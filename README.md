# Star Run: A Tilt Based Handheld Game

## Overview

Star Run is a handheld reaction game built on the Xiao ESP32 C3 using CircuitPython. The player completes tilt gestures within a time limit to progress through ten levels that increase in difficulty. The system uses an ADXL345 accelerometer for motion input, an SSD1306 OLED display for on screen feedback, a NeoPixel LED for visual cues, a piezo buzzer for audio signals, and a rotary encoder for menu interaction. The game demonstrates embedded sensing, filtering, input classification, and real time state management.

The project objective was to create a complete embedded device that integrates hardware, software, and a custom fabricated enclosure while following the project constraints.

## Hardware Used

- Xiao ESP32 C3 microcontroller  
- SSD1306 128x64 OLED display  
- ADXL345 accelerometer  
- Rotary encoder  
- NeoPixel LED  
- Piezo buzzer  
- LiPo battery  
- Physical on and off switch  
- Perfboard with female headers  
- Custom enclosure (3D printed shell and laser cut draftboard layers)

All components are mounted on a perfboard and connected through female headers so that the hardware remains removable.

## Enclosure Fabrication

The enclosure is a combination of 3D printed parts and laser cut draftboard.

### 3D Printed Components
- Outer enclosure sized to fit all electronics  
- Internal standoffs for the microcontroller and display  
- Cutouts for the USB C port and on and off switch  
- Optional rotary encoder side panel based on preferred layout  

### Laser Cut Components
- Four layers of 3.175 mm draftboard cut from an SVG file  
- Layers are screwed together to form the structural body  
- A final top panel is attached with screws to complete the enclosure  

This hybrid construction method provides rigidity and allows easy access to the internal electronics.

## Game Mechanics

### Difficulty Selection
The player rotates the encoder to choose between Easy, Medium, and Hard. If no input is detected for several seconds the highlighted difficulty locks in automatically.

### Gesture Based Gameplay
Each level instructs the player to perform one of four tilt gestures:
- Bank Left  
- Bank Right  
- Nose Up  
- Nose Down  

Gestures are identified by analyzing filtered roll and pitch angles from the accelerometer.

### Scoring
The player receives points for each correct gesture. The score carries across all levels until the player loses. The score is displayed after each level and again on the Game Over or Win screen.

### Game Over and Restart
The game ends when the wrong gesture is performed or time expires. The device shows a Game Over screen and waits for a rotary input to restart the game without power cycling.

### Win Condition
If the player completes all ten levels the device displays a Win screen and plays a celebratory sound sequence.

## How the Program Works

1. **Initialization**  
   The code initializes I2C peripherals, the display, the accelerometer, the encoder, the NeoPixel, and the piezo buzzer.

2. **Accelerometer Calibration**  
   The system measures multiple samples, averages them, identifies the dominant gravity axis, and computes offsets. This creates a consistent reference for calculating roll and pitch.

3. **Filtering and Gesture Detection**  
   The program applies exponential smoothing to sensor data. Gestures are classified by checking angles against thresholds. Debouncing ensures reliable gesture recognition.

4. **Game Loop Structure**  
   The game follows a clear state machine:  
   difficulty menu → wait for neutral → level start → gesture input → score update → next level or Game Over.

5. **Feedback System**  
   The NeoPixel changes color based on the required move, the display updates with level data, and the buzzer plays sounds for success, failure, and win events.

## Repository Contents

A complete repository should include:
- `code.py`  
- `rotary_encoder.py`  
- `/lib` folder containing required CircuitPython libraries  
- System diagram image  
- Circuit diagram image  
- STL and SVG files for the enclosure  
- README.md (this file)

## Summary

Star Run demonstrates a complete embedded system that integrates motion sensing, filtering, user interaction, visual and audio feedback, and custom enclosure fabrication. The project showcases embedded programming, hardware integration, and applied design skills suitable for graduate level coursework.
