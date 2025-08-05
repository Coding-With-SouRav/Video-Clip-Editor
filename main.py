import configparser
import ctypes
import math
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from moviepy import VideoFileClip, concatenate_videoclips
import vlc
from PIL import Image, ImageTk
import os
import platform

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
    ffmpeg_path = os.path.join(base_dir, "bin", "ffmpeg.exe")
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

    try:
        from moviepy.config import change_settings
        change_settings({"FFMPEG_BINARY": ffmpeg_path})

    except ImportError:
        pass

if sys.platform == "win32":
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("som.example.VideoEditor")

def resource_path(relative_path):

    try:
        base_path = sys._MEIPASS

    except Exception:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Resource not found: {full_path}")
    return full_path

class CircularLoader(tk.Canvas):

    def __init__(self, parent, radius=40, dot_radius=5, num_dots=12, speed=100, **kwargs):
        super().__init__(parent, width=radius*2+20, height=radius*2+20, bg=parent.cget('bg'), highlightthickness=0, **kwargs)
        self.radius = radius
        self.dot_radius = dot_radius
        self.num_dots = num_dots
        self.speed = speed
        self.angle = 0
        self.dots = []
        self.create_dots()
        self.animate()

    def create_dots(self):
        self.dots.clear()
        for i in range(self.num_dots):
            angle = 2 * math.pi * i / self.num_dots
            x = self.radius * math.cos(angle) + self.radius + 10
            y = self.radius * math.sin(angle) + self.radius + 10
            dot = self.create_oval(
                x - self.dot_radius, y - self.dot_radius,
                x + self.dot_radius, y + self.dot_radius,
                fill="white", outline=""
            )
            self.dots.append(dot)

    def animate(self):

        if not self.winfo_exists():
            return
        self.angle = (self.angle + 1) % self.num_dots
        for i, dot in enumerate(self.dots):
            index = (i - self.angle) % self.num_dots
            brightness = 255 - int((index / self.num_dots) * 200)
            color = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
            self.itemconfig(dot, fill=color)
        self.after(self.speed, self.animate)

class VideoCutterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Video Cutter Application - By Sourav Bhattacharya")
        self.root.geometry("900x700")
        self.root.configure(bg="#2c3e50")

        try:
            root.iconbitmap(resource_path(r"icons/icon.ico"))

        except Exception as e:
            print("Icon load error:", e)
        self.data_dir = os.path.join(os.path.expanduser("~"), ".VideoEditor")
        os.makedirs(self.data_dir, exist_ok=True)

        if sys.platform == "win32":

            try:
                ctypes.windll.kernel32.SetFileAttributesW(self.data_dir, 2)

            except:
                pass
        self.config_file = os.path.join(self.data_dir, "config.ini")
        self.temp_file = os.path.join(self.data_dir, "temp_clip.mp4")
        self.video_path = None
        self.clip = None
        self.duration = 0
        self.markers = []
        self.deleted_intervals = []
        self.selected_marker_idx = None
        self.was_playing = False
        self.cancel_export = False
        self.dragging_marker_idx = None
        self.hovered_marker_idx = None
        self.canvas_width = 800
        self.canvas_height = 50
        self.all_content_deleted = False
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo_steps = 20
        self.playback_cursor = None
        self.timeline_update_running = False
        self.manual_cursor_time = None

        try:
            self.vlc_instance = vlc.Instance()
            self.vlc_player = self.vlc_instance.media_player_new()

        except Exception as e:
            messagebox.showerror("VLC Error",
                "Failed to initialize VLC. Please install VLC media player from:\n"
                "https://www.videolan.org/\n\nError details: " + str(e))
            root.destroy()
            return
        event_manager = self.vlc_player.event_manager()
        event_manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_video_end)
        self.video_frame = tk.Frame(root, bg="black")
        self.video_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.no_video_label = tk.Label(self.video_frame, text="No Video Loaded", fg="white", bg="black", font=("Helvetica", 45))
        self.no_video_label.place(relx=0.5, rely=0.5, anchor="center")
        self.time_line_frame = tk.Frame(root,bg="#2c3e50")
        self.time_line_frame.pack(fill="x")
        timeline_content = tk.Frame(self.time_line_frame,bg="#2c3e50")
        timeline_content.pack(fill="x", expand=True)
        self.current_time_label = tk.Label(timeline_content, text="00:00:00",bg="#2c3e50", fg='white', width=9, anchor='w')
        self.current_time_label.pack(side="left", padx=(20,0))
        self.canvas = tk.Canvas(timeline_content, bg="#495560", height=self.canvas_height)
        self.canvas.pack(side="left", fill="x", expand=True)
        self.duration_label = tk.Label(timeline_content, text="00:00:00",bg="#2c3e50",fg='white', width=9, anchor='e')
        self.duration_label.pack(side="right", padx=(0,20))
        self.canvas.bind("<Button-3>", self.select_interval)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        self.canvas.bind("<Leave>", lambda e: self.canvas.config(cursor=""))
        self.dragging_cursor = False
        self.root_frame = tk.Frame(root, bg="#2c3e50")
        self.root_frame.pack(fill="x")
        self.controls_frame = tk.Frame(self.root_frame, bg="#2c3e50")
        self.controllar_frame = tk.Frame(self.root_frame, width=self.canvas_width,bg="#2c3e50")
        self.controllar_frame.pack(pady=10)
        upload_video_img= Image.open(resource_path(r"icons\upload_video.png")).resize((35, 35))
        self.upload_video_icon= ImageTk.PhotoImage(upload_video_img)
        skip_back10sec_img= Image.open(resource_path(r"icons\skip_back.png")).resize((30, 30))
        self.skip_back10sec_icon= ImageTk.PhotoImage(skip_back10sec_img)
        skip_fd10sec_img= Image.open(resource_path(r"icons\skip_fd.png")).resize((30, 30))
        self.skip_fd10sec_icon= ImageTk.PhotoImage(skip_fd10sec_img)
        play_img= Image.open(resource_path(r"icons\play.png")).resize((30, 30))
        self.play_icon= ImageTk.PhotoImage(play_img)
        pause_img= Image.open(resource_path(r"icons\pause.png")).resize((30, 30))
        self.pause_icon= ImageTk.PhotoImage(pause_img)
        stop_img= Image.open(resource_path(r"icons\stop.png")).resize((30, 30))
        self.stop_icon= ImageTk.PhotoImage(stop_img)
        export_img= Image.open(resource_path(r"icons\export.png")).resize((35, 35))
        self.export_icon= ImageTk.PhotoImage(export_img)
        volume_up_img= Image.open(resource_path(r"icons\volume_up.png")).resize((35, 35))
        self.volume_up_icon= ImageTk.PhotoImage(volume_up_img)
        volume_down_img= Image.open(resource_path(r"icons\volume_down.png")).resize((35, 35))
        self.volume_down_icon= ImageTk.PhotoImage(volume_down_img)
        split_img= Image.open(resource_path(r"icons\split.png")).resize((35, 35))
        self.split_icon= ImageTk.PhotoImage(split_img)
        delete_img= Image.open(resource_path(r"icons\delete.png")).resize((35, 35))
        self.delete_icon= ImageTk.PhotoImage(delete_img)
        self.load_btn = tk.Button(self.controllar_frame, image=self.upload_video_icon,bd=0, bg="#2c3e50", activebackground="#3c6187",command=self.load_video)
        self.load_btn.pack(side='left', padx=5)
        self.split_btn = tk.Button(self.controllar_frame, image=self.split_icon,bd=0, bg="#2c3e50", activebackground="#3c6187",command=self.split_at_current_time)
        self.delete_btn = tk.Button(self.controllar_frame, image=self.delete_icon,bd=0,bg="#2c3e50",activebackground="#3c6187",command=self.delete_selected_interval)
        self.save_btn = tk.Button(self.controllar_frame, image=self.export_icon,bd=0, bg="#2c3e50",activebackground="#3c6187", command=self.save_video)
        self.back_btn = tk.Button(self.controls_frame, image=self.skip_back10sec_icon,bd=0, bg="#2c3e50", activebackground="#3c6187",command=self.skip_backward)
        self.back_btn.grid(row=0, column=0, padx=5)
        self.play_pause_btn = tk.Button(self.controls_frame,image=self.pause_icon,bd=0,bg="#2c3e50",activebackground="#3c6187",  command=self.play_pause)
        self.play_pause_btn.grid(row=0, column=1, padx=5)
        self.stop_btn = tk.Button(self.controls_frame, image=self.stop_icon,bg="#2c3e50",bd=0,activebackground="#3c6187",  command=self.stop_video)
        self.stop_btn.grid(row=0, column=3, padx=5)
        self.forward_btn = tk.Button(self.controls_frame,image=self.skip_fd10sec_icon,bg="#2c3e50",bd=0,activebackground="#3c6187", command=self.skip_forward)
        self.forward_btn.grid(row=0, column=4, padx=5)
        self.root.bind("<Configure>", self.on_window_resize)
        self.root.bind("<Control-z>", self.undo_delete)
        self.root.bind("<Control-y>", self.redo_delete)
        self.root.bind("<Control-Z>", self.undo_delete)
        self.root.bind("<Control-Y>", self.redo_delete)
        self.load_window_geometry()
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_window_geometry(self):

        if os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config.read(self.config_file)

            if "Geometry" in config:
                geometry = config["Geometry"].get("size", "")
                state = config["Geometry"].get("state", "normal")

                if geometry:
                    self.root.geometry(geometry)
                    self.root.update_idletasks()
                    self.root.update()

                if state == "zoomed":
                    self.root.state("zoomed")
                elif state == "iconic":
                    self.root.iconify()

    def save_window_geometry(self):
        config = configparser.ConfigParser()
        config["Geometry"] = {
            "size": self.root.geometry(),
            "state": self.root.state()
        }

        with open(self.config_file, "w") as f:
            config.write(f)

    def on_close(self):
        self.save_window_geometry()

        try:

            if self.vlc_player:
                self.vlc_player.stop()

        except:
            pass
        root.destroy()
        os._exit(0)

    def on_video_end(self, event):
        self.root.after(0, self.reset_to_beginning)

    def reset_to_beginning(self):

        if self.vlc_player:
            self.vlc_player.stop()
            self.vlc_player.set_time(0)
            self.manual_cursor_time = 0
            self.draw_timeline()
            self.current_time_label.config(text=self.format_time(0))
            self.play_pause_btn.config(image=self.play_icon)

    def load_video(self):
        self.undo_stack = []
        self.redo_stack = []
        path = filedialog.askopenfilename(filetypes=[("Video files", "*.mp4 *.avi *.mov")])

        if not path:
            return
        self.video_path = path
        self.clip = VideoFileClip(self.video_path)
        self.duration = self.clip.duration
        self.markers = []
        self.deleted_intervals = []
        self.selected_marker_idx = None
        self.manual_cursor_time = None
        self.all_content_deleted = False
        self.draw_timeline()
        media = self.vlc_instance.media_new(self.video_path)
        self.vlc_player.set_media(media)
        self.no_video_label.place_forget()

        if platform.system() == "Windows":
            self.vlc_player.set_hwnd(self.video_frame.winfo_id())
        elif platform.system() == "Linux":
            self.vlc_player.set_xwindow(self.video_frame.winfo_id())
        elif platform.system() == "Darwin":
            self.vlc_player.set_nsobject(self.video_frame.winfo_id())
        self.controls_frame.pack(pady=10)
        self.controllar_frame.pack_forget()
        self.controllar_frame.pack(pady=10)
        self.split_btn.pack(side='left', padx=5)
        self.delete_btn.pack(side='left', padx=5)
        self.save_btn.pack(side='left', padx=5)
        self.vlc_player.play()
        self.play_pause_btn.config(image=self.pause_icon)
        self.start_timeline_update()

    def draw_timeline(self):

        if not self.clip:
            return
        self.canvas.delete("all")
        total_virtual_duration = self.get_virtual_duration()

        if total_virtual_duration <= 0:
            return
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        timeline_width = int((total_virtual_duration / self.duration) * (canvas_width - 20))
        start_x = (canvas_width - timeline_width) // 2
        end_x = start_x + timeline_width
        self.canvas.create_line(start_x, self.canvas_height // 2, end_x, self.canvas_height // 2, width=10, fill="black")
        for marker in self.markers:
            virtual_marker_time = self.to_virtual_time(marker)

            if virtual_marker_time is None:
                continue
            x = start_x + (virtual_marker_time / total_virtual_duration) * timeline_width
            self.canvas.create_line(x, 20, x, self.canvas_height - 20, fill="red", width=2)

        if self.selected_marker_idx is not None and self.selected_marker_idx + 1 < len(self.markers):
            start = self.markers[self.selected_marker_idx]
            end = self.markers[self.selected_marker_idx + 1]
            v_start = self.to_virtual_time(start)
            v_end = self.to_virtual_time(end)

            if v_start is not None and v_end is not None:
                x1 = start_x + (v_start / total_virtual_duration) * timeline_width
                x2 = start_x + (v_end / total_virtual_duration) * timeline_width
                self.canvas.create_rectangle(x1, 0, x2, self.canvas_height, fill="yellow", stipple="gray50")
        cursor_time = self.manual_cursor_time if self.manual_cursor_time is not None else self.get_current_time()
        virtual_cursor_time = self.to_virtual_time(cursor_time)

        if virtual_cursor_time is not None:
            x = start_x + (virtual_cursor_time / total_virtual_duration) * timeline_width
            self.playback_cursor = self.canvas.create_line(x, 0, x, self.canvas_height, fill="#08f718", width=2)

    def get_virtual_duration(self):
        deleted_total = sum(end - start for start, end in self.deleted_intervals)
        return self.duration - deleted_total

    def start_timeline_update(self):
        self.timeline_update_running = True
        self.update_timeline_cursor()

    def update_timeline_cursor(self):

        if not self.timeline_update_running or not self.clip:
            return
        current_time = self.get_current_time()
        current_time = max(0, current_time)
        for start, end in self.deleted_intervals:

            if start <= current_time <= end:
                self.vlc_player.set_time(int((end + 0.05) * 1000))
                self.root.after(0, self.ensure_playing)
                self.root.after(0, self.update_timeline_cursor)
                return
        self.manual_cursor_time = None
        self.draw_timeline()
        virtual_time = self.to_virtual_time(current_time)

        if virtual_time is not None and virtual_time >= 0:
            self.current_time_label.config(text=self.format_time(virtual_time))
        else:
            self.current_time_label.config(text="00:00:00")

        if self.get_virtual_duration() <= 0:
            return
        self.duration_label.config(text=self.format_time(self.get_virtual_duration()))
        self.root.after(100, self.update_timeline_cursor)

    def to_virtual_time(self, real_time):
        virtual_time = real_time
        for start, end in self.deleted_intervals:

            if real_time > end:
                virtual_time -= (end - start)
            elif start <= real_time <= end:
                return None
            else:
                break
        return virtual_time

    def to_real_time(self, virtual_time):
        real_time = virtual_time
        for start, end in sorted(self.deleted_intervals):

            if real_time >= start:
                real_time += (end - start)
            else:
                break
        return real_time

    def ensure_playing(self):

        if self.vlc_player.get_state() != vlc.State.Playing:
            self.vlc_player.play()

    def get_current_time(self):
        return self.vlc_player.get_time() / 1000 if self.vlc_player else 0

    def seek_to_click(self, event):

        if not self.clip:
            return
        rel_x = event.x - 10
        total_virtual_duration = self.get_virtual_duration()
        virtual_time = (rel_x / (self.canvas_width - 20)) * total_virtual_duration
        virtual_time = max(0, min(virtual_time, total_virtual_duration))
        real_time = self.to_real_time(virtual_time)
        self.vlc_player.set_time(int(real_time * 1000))
        self.manual_cursor_time = real_time
        self.draw_timeline()

    def split_at_current_time(self):

        if not self.clip:
            return
        time_pos = self.get_current_time()
        self.markers.append(time_pos)
        self.markers = sorted(list(set(self.markers)))
        self.draw_timeline()

    def select_interval(self, event):

        if not self.clip:
            return

        if len(self.markers) < 2:
            return
        rel_x = event.x - 10
        total_virtual_duration = self.get_virtual_duration()
        virtual_time_clicked = (rel_x / (self.canvas_width - 20)) * total_virtual_duration
        real_time_clicked = self.to_real_time(virtual_time_clicked)
        for i in range(len(self.markers) - 1):
            start, end = self.markers[i], self.markers[i + 1]

            if start <= real_time_clicked <= end:
                self.selected_marker_idx = i
                break
        else:
            self.selected_marker_idx = None
        self.draw_timeline()

    def delete_selected_interval(self):

        if self.selected_marker_idx is None or self.selected_marker_idx + 1 >= len(self.markers):
            messagebox.showwarning("No interval selected", "Right-click between two markers to select an interval.")
            return
        self.push_undo_state()
        start = self.markers[self.selected_marker_idx]
        end = self.markers[self.selected_marker_idx + 1]
        self.deleted_intervals.append((start, end))
        self.markers.pop(self.selected_marker_idx + 1)
        self.markers.pop(self.selected_marker_idx)
        self.selected_marker_idx = None
        self.play_pause_btn.config(image=self.pause_icon)
        total_virtual_duration = self.get_virtual_duration()

        if total_virtual_duration <= 0:
            self.all_content_deleted = True
            messagebox.showinfo("No Content Left", "All parts of the video have been deleted. Nothing remains to export.")
            self.play_pause_btn.config(image=self.play_icon)
            self.stop_video()
            self.vlc_player.set_time(0)
            self.manual_cursor_time = 0
            self.draw_timeline()
            return
        self.draw_timeline()

    def save_video(self):

        if not self.clip:
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4 files", "*.mp4")])

        if not save_path:
            return
        intervals = []
        last = 0
        for start, end in sorted(self.deleted_intervals):

            if last < start:
                intervals.append((last, start))
            last = end

        if last < self.duration:
            intervals.append((last, self.duration))

        if not intervals:
            messagebox.showinfo("Nothing to Save", "No segments selected for saving.")
            return
        self.cancel_export = False
        self.play_pause()
        self.controls_frame.pack_forget()
        self.controllar_frame.pack_forget()
        self.show_saving_animation()

        def export():

            try:
                temp_clips = []
                for idx, (start, end) in enumerate(intervals):

                    if self.cancel_export:
                        raise Exception("Export cancelled by user.")
                    subclip = self.clip.subclipped(start, end)
                    subclip.write_videofile(self.temp_file, audio=True,  logger=None)
                    temp_clips.append(VideoFileClip(self.temp_file))

                if self.cancel_export:
                    raise Exception("Export cancelled by user.")
                final_clip = concatenate_videoclips(temp_clips)
                final_clip.write_videofile(save_path, logger=None)
                self.root.after(0, lambda: messagebox.showinfo("Saved", f"Edited video saved to:\n{save_path}"))
                self.controls_frame.pack(pady=10)
                self.controllar_frame.pack(pady=10)

            except Exception as e:

                if str(e) == "Export cancelled by user.":
                    self.root.after(0, lambda: messagebox.showinfo("Cancelled", "Video export cancelled."))
                    self.controls_frame.pack(pady=10)
                    self.controllar_frame.pack(pady=10)
                else:
                    self.root.after(0, lambda error = e: messagebox.showerror("Error", f"Failed to save video:\n{error}"))
                    self.controls_frame.pack(pady=10)
                    self.controllar_frame.pack(pady=10)

            finally:
                self.root.after(0, self.loding_animation_frame.destroy)
        threading.Thread(target=export).start()

    def play_pause(self):

        if self.all_content_deleted:
            messagebox.showwarning("Playback Blocked", "Cannot play. All parts of the video have been deleted.")
            return

        if self.vlc_player:
            state = self.vlc_player.get_state()

            if state == vlc.State.Ended or self.get_current_time() >= self.duration - 0.05:
                self.reset_to_beginning()
                self.vlc_player.play()
            elif state == vlc.State.Playing:
                self.vlc_player.pause()
                self.play_pause_btn.config(image=self.play_icon)
            else:
                self.vlc_player.play()
                self.play_pause_btn.config(image=self.pause_icon)

    def stop_video(self):

        if self.all_content_deleted:
            return

        if self.vlc_player:
            self.vlc_player.stop()
            self.play_pause_btn.config(image=self.play_icon)

    def skip_backward(self):

        if self.all_content_deleted:
            return

        if self.vlc_player:
            was_playing = self.vlc_player.get_state() == vlc.State.Playing
            current = self.vlc_player.get_time() / 1000
            new_time = max(0, current - 10)
            self.vlc_player.set_time(int(new_time * 1000))
            self.manual_cursor_time = new_time
            self.draw_timeline()

            def finalize_seek():
                current_state = self.vlc_player.get_state()

                if was_playing:
                    self.vlc_player.play()
                    self.play_pause_btn.config(image=self.pause_icon)
                else:

                    if current_state == vlc.State.Playing:
                        self.vlc_player.pause()
                    self.play_pause_btn.config(image=self.play_icon)
            self.root.after(100, finalize_seek)

    def skip_forward(self):

        if self.all_content_deleted:
            return

        if self.vlc_player:
            was_playing = self.vlc_player.get_state() == vlc.State.Playing
            current = self.vlc_player.get_time() / 1000
            new_time = min(self.duration, current + 10)
            self.vlc_player.set_time(int(new_time * 1000))
            self.manual_cursor_time = new_time
            self.draw_timeline()

            def finalize_seek():
                current_state = self.vlc_player.get_state()

                if was_playing:
                    self.vlc_player.play()
                    self.play_pause_btn.config(image=self.pause_icon)
                else:

                    if current_state == vlc.State.Playing:
                        self.vlc_player.pause()
                    self.play_pause_btn.config(image=self.play_icon)
            self.root.after(100, finalize_seek)

    def format_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}"

    def on_press(self, event):
        marker_idx = self.get_marker_near_cursor(event.x)

        if marker_idx is not None:
            self.dragging_marker_idx = marker_idx
            return

        if not self.clip:
            return
        was_playing = self.vlc_player.get_state() == vlc.State.Playing
        rel_x = event.x - 10
        total_virtual_duration = self.get_virtual_duration()
        virtual_time = (rel_x / (self.canvas_width - 20)) * total_virtual_duration
        virtual_time = max(0, min(virtual_time, total_virtual_duration))
        real_time = self.to_real_time(virtual_time)
        self.vlc_player.set_time(int(real_time * 1000))
        self.manual_cursor_time = real_time
        self.play_pause_btn.config(image=self.play_icon)
        self.draw_timeline()

        if not was_playing:
            self.vlc_player.pause()
        cursor_time = self.manual_cursor_time if self.manual_cursor_time is not None else self.get_current_time()
        virtual_cursor = self.to_virtual_time(cursor_time)
        timeline_width = int((total_virtual_duration / self.duration) * (self.canvas_width - 20))
        start_x = (self.canvas_width - timeline_width) // 2
        cursor_x = start_x + (virtual_cursor / total_virtual_duration) * timeline_width

        if abs(cursor_x - event.x) <= 5:
            self.dragging_cursor = True

    def on_drag(self, event):

        if self.dragging_marker_idx is not None:
            rel_x = event.x - 10
            total_virtual_duration = self.get_virtual_duration()
            virtual_time = (rel_x / (self.canvas_width - 20)) * total_virtual_duration
            virtual_time = max(0, min(virtual_time, total_virtual_duration))
            real_time = self.to_real_time(virtual_time)

            if self.dragging_marker_idx > 0 and real_time <= self.markers[self.dragging_marker_idx - 1] + 0.1:
                return

            if self.dragging_marker_idx < len(self.markers) - 1 and real_time >= self.markers[self.dragging_marker_idx + 1] - 0.1:
                return
            self.markers[self.dragging_marker_idx] = real_time
            self.draw_timeline()
            return

        if self.clip:
            was_playing = self.vlc_player.get_state() == vlc.State.Playing
            rel_x = event.x - 10
            total_virtual_duration = self.get_virtual_duration()
            virtual_time = (rel_x / (self.canvas_width - 20)) * total_virtual_duration
            virtual_time = max(0, min(virtual_time, total_virtual_duration))
            real_time = self.to_real_time(virtual_time)
            self.vlc_player.set_time(int(real_time * 1000))
            self.manual_cursor_time = real_time
            self.draw_timeline()

            if not was_playing:
                self.vlc_player.pause()

    def on_release(self, event):

        if self.dragging_marker_idx is not None:
            self.dragging_marker_idx = None
            return

        if self.dragging_cursor:
            self.dragging_cursor = False
            self.manual_cursor_time = None

            if self.was_playing:
                self.ensure_playing()
            else:
                self.vlc_player.pause()

    def on_window_resize(self, event):

        if event.widget == self.root:
            self.canvas_width = self.canvas.winfo_width()
            self.canvas_height = self.canvas.winfo_height()
            self.draw_timeline()

            if platform.system() == "Windows":
                self.vlc_player.set_hwnd(self.video_frame.winfo_id())
            elif platform.system() == "Linux":
                self.vlc_player.set_xwindow(self.video_frame.winfo_id())
            elif platform.system() == "Darwin":
                self.vlc_player.set_nsobject(self.video_frame.winfo_id())

    def show_saving_animation(self):
        self.loding_animation_frame = tk.Frame(self.root_frame, bg="#2c3e50", highlightthickness=0)
        self.loding_animation_frame.pack()
        self.current_loader = CircularLoader(
            self.loding_animation_frame,
            radius=20,
            dot_radius=1.5,
            speed=50,
        )
        self.current_loader.pack(side=tk.LEFT,anchor='center', padx=20)
        cancel_frame = tk.Frame(self.loding_animation_frame, bg="#2c3e50", highlightthickness=0)
        cancel_frame.pack(side=tk.LEFT, padx=20)
        self.calcel_label= tk.Label(cancel_frame, text="Downloading....\nPlease wait for sometime.", font=("Helvetica", 12), bg='#2c3e50', fg='white', highlightthickness=0)
        self.calcel_label.pack(pady=(10,0))
        cancel_btn = tk.Button(cancel_frame, text="Cancel", font=("Helvetica", 12), bg='red', fg='white', highlightthickness=0, bd=0, activebackground="lemon chiffon", activeforeground="black", command=self.cancel_export_process)
        cancel_btn.pack(pady=(10,10))

    def cancel_export_process(self):
        confirm = messagebox.askyesno("Cancel Export", "Are you sure you want to cancel the video export?")

        if confirm:
            self.calcel_label.config(text="Cancelling the Download process... \nPlease wait for sometime.")
            self.cancel_export = True

    def on_canvas_motion(self, event):

        if not self.clip:
            return
        idx = self.get_marker_near_cursor(event.x)

        if idx is not None:
            self.canvas.config(cursor="sb_h_double_arrow")
            self.hovered_marker_idx = idx
        else:
            self.canvas.config(cursor="")
            self.hovered_marker_idx = None

    def get_marker_near_cursor(self, x):

        if not self.markers:
            return None
        canvas_width = self.canvas.winfo_width()
        total_virtual_duration = self.get_virtual_duration()
        timeline_width = int((total_virtual_duration / self.duration) * (canvas_width - 20))
        start_x = (canvas_width - timeline_width) // 2
        for idx, marker in enumerate(self.markers):
            virtual_time = self.to_virtual_time(marker)

            if virtual_time is None:
                continue
            marker_x = start_x + (virtual_time / total_virtual_duration) * timeline_width

            if abs(x - marker_x) <= 6:
                return idx
        return None

    def capture_state(self):
        return {
            'markers': list(self.markers),
            'deleted_intervals': list(self.deleted_intervals),
            'all_content_deleted': self.all_content_deleted
        }

    def restore_state(self, state):
        self.markers = list(state['markers'])
        self.deleted_intervals = list(state['deleted_intervals'])
        self.all_content_deleted = state['all_content_deleted']
        self.selected_marker_idx = None
        self.draw_timeline()

    def push_undo_state(self):
        state = self.capture_state()

        if len(self.undo_stack) >= self.max_undo_steps:
            self.undo_stack.pop(0)
        self.undo_stack.append(state)
        self.redo_stack = []

    def undo_delete(self, event=None):

        if not self.undo_stack:
            return
        self.redo_stack.append(self.capture_state())
        state = self.undo_stack.pop()
        self.restore_state(state)

        if self.all_content_deleted:
            self.stop_video()
        else:
            self.play_pause_btn.config(image=self.pause_icon)

    def redo_delete(self, event=None):

        if not self.redo_stack:
            return
        self.undo_stack.append(self.capture_state())
        state = self.redo_stack.pop()
        self.restore_state(state)

        if self.all_content_deleted:
            self.stop_video()
        else:
            self.play_pause_btn.config(image=self.pause_icon)

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoCutterApp(root)
    root.mainloop()
