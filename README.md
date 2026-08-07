

### Key Features:
1. **Video Editing Core Functionality**:
   - Split videos at precise timestamps
   - Delete selected intervals between markers
   - Export edited videos (non-deleted segments concatenated)
   - Undo/Redo operations (Ctrl+Z/Ctrl+Y)

2. **Playback Controls**:
   - Play/Pause toggle
   - Stop button
   - 10-second skip forward/backward
   - Timeline scrubbing (click+drag)

3. **Visual Timeline**:
   - Interactive markers (red lines)
   - Playback cursor (green line)
   - Interval selection (yellow highlight)
   - Marker dragging for position adjustment

4. **Technical Implementation**:
   - VLC integration for hardware-accelerated playback
   - MoviePy for video processing/export
   - Persistent window state/config
   - Resource handling for PyInstaller bundles
   - Cross-platform support (Windows/Linux/macOS)

5. **User Experience**:
   - Progress indicator during exports
   - Cancelable export operations
   - Comprehensive error handling
   - Visual feedback for all actions
   - Time formatting (HH:MM:SS)

### UI Layout & Components:
1. **Video Display Area** (Top Section):
   - Black background frame
   - "No Video Loaded" placeholder text
   - VLC player embedded when video loaded

2. **Timeline Panel** (Middle Section):
   - Current time label (left)
   - Canvas-based timeline visualization:
     - Black line representing video duration
     - Red markers for split points
     - Green playback cursor
     - Yellow highlighted selections
   - Total duration label (right)

3. **Control Panel** (Bottom Section):
   - **Action Buttons** (Icon-based):
     - Upload video (folder icon)
     - Split (scissors icon)
     - Delete (trash icon)
     - Export (save icon)
   - **Playback Controls**:
     - Skip backward (left arrow)
     - Play/Pause toggle
     - Stop button
     - Skip forward (right arrow)
   - **Progress Indicator** (During export):
     - Circular loader animation
     - Cancel button

### Special Interactions:
1. **Timeline Controls**:
   - Left-click: Seek to position
   - Right-click: Select interval
   - Click+drag: Move playback cursor
   - Marker hover: Horizontal resize cursor
   - Marker drag: Adjust split positions

2. **Keyboard Shortcuts**:
   - Ctrl+Z: Undo deletion
   - Ctrl+Y: Redo deletion

3. **Error Handling**:
   - VLC initialization errors
   - Export cancellation
   - Empty video exports
   - Resource loading issues

4. **State Management**:
   - Remembers window size/position
   - Persistent configuration in hidden directory
   - Undo/Redo stack (20-step history)

### Visual Design:
- Color Scheme: Dark theme (#2c3e50 background)
- Custom icons for all actions
- Animated circular loader
- Visual feedback for:
  - Interval selection
  - Playback position
  - Export progress
  - Deletion states

This application provides a streamlined interface for precise video editing operations, combining professional-grade video processing libraries with an intuitive timeline-based UI. The dark theme reduces eye strain during extended editing sessions, while the icon-based controls ensure quick access to core functionality.


<!-- AUTO UPDATE -->
Last maintenance: 2026-08-07 04:39 UTC
