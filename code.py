import time, random, math
import board, busio, displayio, terminalio
from adafruit_display_text import label
import i2cdisplaybus
import adafruit_displayio_ssd1306
import adafruit_adxl34x
import neopixel
import pwmio
from rotary_encoder import RotaryEncoder

DEBUG = True

# ============================================================================
# HARDWARE PIN CONFIGURATION
# ============================================================================
I2C_SDA = board.SDA
I2C_SCL = board.SCL

ENC_A   = board.D3
ENC_B   = board.D0
NEO_PIN = board.D1
PIEZO_PIN = board.D2

# ============================================================================
# GAME CONSTANTS
# ============================================================================
MAX_LEVELS = 10
BASE_SCORE_PER_LEVEL = 100

# NeoPixel color presets
OFF    = (0,0,0)
FLYING = (0,0,20)
WARN   = (20,10,0)
GOOD   = (0,25,0)
BAD    = (25,0,0)
WIN    = (10,0,20)

# Tilt gesture labels
MOVE_BANK_LEFT   = "BANK LEFT"
MOVE_BANK_RIGHT  = "BANK RIGHT"
MOVE_NOSE_UP     = "NOSE UP"
MOVE_NOSE_DOWN   = "NOSE DOWN"

ALL_MOVES = [
    MOVE_BANK_LEFT,
    MOVE_BANK_RIGHT,
    MOVE_NOSE_UP,
    MOVE_NOSE_DOWN
]

# LED color for each gesture
MOVE_COLORS = {
    MOVE_BANK_LEFT:  (0, 0, 25),
    MOVE_BANK_RIGHT: (0, 0, 25),
    MOVE_NOSE_UP:    (0, 25, 0),
    MOVE_NOSE_DOWN:  (25, 25, 0),
}

# Difficulty definitions
DIFFICULTIES = [
    {"name":"EASY",   "base_time":6.0, "per_level":0.25, "score_bonus":0},
    {"name":"MEDIUM", "base_time":4.5, "per_level":0.20, "score_bonus":50},
    {"name":"HARD",   "base_time":3.2, "per_level":0.15, "score_bonus":100},
]

# ============================================================================
# SOUND HELPER
# ============================================================================
def tone(pin, freq, duration, duty=45000):
    """
    Simple piezo buzzer tone generator.
    """
    try:
        b = pwmio.PWMOut(pin, frequency=freq, duty_cycle=duty)
        time.sleep(duration)
        b.deinit()
    except:
        pass
    time.sleep(0.01)

# ============================================================================
# DISPLAY WRAPPER
# ============================================================================
class Display:
    """
    Cleaner OLED formatting helper. Handles 4-line screens.
    """
    def __init__(self, disp):
        self.disp = disp

    def show(self, l1="", l2="", l3="", l4=""):
        g = displayio.Group()
        ys = [12,28,44,58]
        ls = [l1,l2,l3,l4]

        for i,txt in enumerate(ls):
            if txt:
                t = label.Label(
                    terminalio.FONT,
                    text=txt,
                    color=0xFFFFFF,
                    anchor_point=(0.5,0.5),
                    anchored_position=(64, ys[i])
                )
                g.append(t)

        self.disp.root_group = g

    def show_ready(self, level):
        self.show(f"LEVEL {level}", "", "Center device…", "Stay still")

    def show_level(self, level, move, remaining, score):
        self.show(
            f"LEVEL {level}/{MAX_LEVELS}",
            f"DO: {move}",
            f"Time: {remaining:.1f}s",
            f"Score: {score}"
        )

    def show_difficulty(self, name, score):
        self.show(
            "STAR RUN",
            f"Mode: {name}",
            f"Score: {score}",
            "Rotate encoder"
        )

# ============================================================================
# TILT DETECTOR
# ============================================================================
class TiltDetector:
    """
    Handles ADXL345 calibration, filtering, angle extraction, categorizing
    roll/pitch movements into BANK LEFT/RIGHT or NOSE UP/DOWN gestures.
    """

    def __init__(self, accel):
        self.acc = accel
        self.alpha = 0.2  # smoothing filter alpha

        # Gesture thresholds
        self.dead_angle   = 10.0
        self.roll_thresh  = 12.0
        self.pitch_thresh = 18.0
        self.cross_limit  = 15.0
        self.samples_required = 2

        # Debouncing
        self._last_candidate = None
        self._candidate_count = 0

        print("\n=== TILT CALIBRATION ===")
        time.sleep(1)
        self._calibrate()

        # Initialize filtered values
        self.xf, self.yf, self.zf = self.acc.acceleration

    # ----------------------------------------------------------------------
    # Calibration collects averages and figures out which axis is gravity
    # ----------------------------------------------------------------------
    def _calibrate(self):
        samples = 50
        sx=sy=sz=0

        for _ in range(samples):
            x,y,z = self.acc.acceleration
            sx+=x; sy+=y; sz+=z
            time.sleep(0.01)

        ax=sx/samples; ay=sy/samples; az=sz/samples
        print(f"Avg: X={ax:.2f} Y={ay:.2f} Z={az:.2f}")

        mags = [abs(ax), abs(ay), abs(az)]
        self.gravity_axis = mags.index(max(mags))
        axes = ["X","Y","Z"]
        print(f"Gravity axis: {axes[self.gravity_axis]}")

        # Zero-out the gravity axis, store offsets for the others
        self.x_off = ax if self.gravity_axis!=0 else 0
        self.y_off = ay if self.gravity_axis!=1 else 0
        self.z_off = az if self.gravity_axis!=2 else 0

        # Determine which axes define roll/pitch
        if self.gravity_axis==2:
            self.roll_plane=("X","Z")
            self.pitch_plane=("Y","Z")
        elif self.gravity_axis==1:
            self.roll_plane=("X","Y")
            self.pitch_plane=("Z","Y")
        else:
            self.roll_plane=("Y","X")
            self.pitch_plane=("Z","X")

        print(f"ROLL:  {self.roll_plane}")
        print(f"PITCH: {self.pitch_plane}")

    # ----------------------------------------------------------------------
    # Read + filter acceleration
    # ----------------------------------------------------------------------
    def _update(self):
        x,y,z = self.acc.acceleration
        x -= self.x_off; y -= self.y_off; z -= self.z_off

        a = self.alpha
        self.xf = a*x + (1-a)*self.xf
        self.yf = a*y + (1-a)*self.yf
        self.zf = a*z + (1-a)*self.zf

    def _g(self, axis):
        return {"X":self.xf, "Y":self.yf, "Z":self.zf}[axis]

    # ----------------------------------------------------------------------
    # Convert filtered acceleration → roll/pitch angles → gesture detection
    # ----------------------------------------------------------------------
    def read(self):
        self._update()

        t_roll  = self._g(self.roll_plane[0])
        g_roll  = self._g(self.roll_plane[1])
        roll = math.degrees(math.atan2(t_roll, g_roll))

        t_pitch = self._g(self.pitch_plane[0])
        g_pitch = self._g(self.pitch_plane[1])
        pitch = math.degrees(math.atan2(t_pitch, g_pitch))

        if DEBUG:
            print(f"[TILT] Roll={roll:5.1f}°  Pitch={pitch:5.1f}°")

        # Neutral = no gesture
        if abs(roll)<self.dead_angle and abs(pitch)<self.dead_angle:
            self._last_candidate=None
            self._candidate_count=0
            return None

        candidate=None

        # BANK gestures → dominated by roll
        if abs(roll)>=self.roll_thresh and abs(pitch)<=self.cross_limit:
            candidate = MOVE_BANK_RIGHT if roll>0 else MOVE_BANK_LEFT

        # NOSE gestures → dominated by pitch
        elif abs(pitch)>=self.pitch_thresh and abs(roll)<=self.cross_limit:
            candidate = MOVE_NOSE_DOWN if pitch>0 else MOVE_NOSE_UP

        # If not clean → no gesture
        if candidate is None:
            self._last_candidate=None
            self._candidate_count=0
            return None

        # Gesture debouncing
        if candidate == self._last_candidate:
            self._candidate_count += 1
        else:
            self._last_candidate = candidate
            self._candidate_count = 1

        # Fire once stable
        if self._candidate_count >= self.samples_required:
            self._last_candidate=None
            self._candidate_count=0
            return candidate

        return None

# ============================================================================
# STAR RUN GAME ENGINE
# ============================================================================
class StarRun:
    """
    Core game engine: difficulty selection, level control,
    gesture reading, scoring, win/lose screens.
    """

    DIFFICULTY_IDLE_TIMEOUT = 6
    END_SCREEN_DELAY = 3

    def __init__(self):
        # ----- Display setup -----
        displayio.release_displays()
        i2c = busio.I2C(I2C_SCL, I2C_SDA)
        bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
        oled = adafruit_displayio_ssd1306.SSD1306(bus, width=128, height=64)
        self.disp = Display(oled)

        # ----- Accelerometer -----
        accel = adafruit_adxl34x.ADXL345(i2c)
        self.tilt = TiltDetector(accel)

        # ----- Encoder -----
        self.enc = RotaryEncoder(ENC_A, ENC_B, debounce_ms=3, pulses_per_detent=3)

        # ----- LED + Piezo -----
        self.pixel = neopixel.NeoPixel(NEO_PIN, 1, brightness=0.3, auto_write=False)
        self.piezo = PIEZO_PIN

        # ----- Game State -----
        self.diff_idx = 0
        self.score = 0

    # Short helper
    def px(self, c):
        self.pixel[0] = c
        self.pixel.show()

    # ----------------------------------------------------------------------
    # Neutral detection (device resting)
    # ----------------------------------------------------------------------
    def wait_neutral(self):
        stable=0
        needed=8
        print("WAITING FOR NEUTRAL…")

        while True:
            r=self.tilt.read()
            if r is None:
                stable+=1
                if stable>=needed:
                    print("NEUTRAL LOCKED")
                    return
            else:
                stable=0
            time.sleep(0.02)

    # ----------------------------------------------------------------------
    # Wait for encoder twist
    # ----------------------------------------------------------------------
    def wait_for_rotate(self):
        last=self.enc.position
        while True:
            if self.enc.update():
                if self.enc.position != last:
                    tone(self.piezo,700,0.07)
                    return
            time.sleep(0.03)

    # ----------------------------------------------------------------------
    # Difficulty Selection Screen
    # ----------------------------------------------------------------------
    def select_difficulty(self):
        idx = self.diff_idx
        idle = time.monotonic()
        last_step = time.monotonic()   # anti-bounce UI-level timing

        while True:
            d = DIFFICULTIES[idx]
            self.disp.show_difficulty(d["name"], self.score)
            self.px(FLYING if int(time.monotonic()*2)%2 == 0 else OFF)

            # ---- READ ROTARY USING SAFE DELTA MODE ----
            if self.enc.update():  
                delta = self.enc.get_delta()   # MUCH more reliable than position math

                # only allow change every 150ms to prevent multi-jumps
                if delta != 0 and (time.monotonic() - last_step) > 0.15:
                    if delta > 0:
                        idx = (idx + 1) % len(DIFFICULTIES)
                    else:
                        idx = (idx - 1) % len(DIFFICULTIES)

                    last_step = time.monotonic()
                    idle = time.monotonic()
                    tone(self.piezo, 800, 0.05)

            # ---- Idle timeout to select difficulty ----
            if time.monotonic() - idle > self.DIFFICULTY_IDLE_TIMEOUT:
                self.diff_idx = idx
                return

            time.sleep(0.02)


            # NEW: 6 seconds instead of 2
            if time.monotonic() - idle > self.DIFFICULTY_IDLE_TIMEOUT:
                self.diff_idx = idx
                return
        
            time.sleep(0.05)

    # ----------------------------------------------------------------------
    # Level gameplay
    # ----------------------------------------------------------------------
    def play_level(self, lvl):
        move = random.choice(ALL_MOVES)
        d = DIFFICULTIES[self.diff_idx]

        # Calculate allowed time for this level
        time_limit = max(0.9, d["base_time"] - d["per_level"]*(lvl-1))

        print(f"\n=== LEVEL {lvl} — NEED {move} ===")

        # READY (show directions *without* revealing the move yet)
        self.disp.show_ready(lvl)
        self.px(WARN)
        self.wait_neutral()
        self.px(OFF)
        time.sleep(0.25)

        # Start timer
        start = time.monotonic()

        # Actual gameplay loop
        while True:
            now = time.monotonic()
            remaining = time_limit - (now - start)

            if remaining <= 0:
                print("TIMEOUT")
                return False

            # Show move during gameplay
            self.disp.show_level(lvl, move, remaining, self.score)
            self.px(MOVE_COLORS[move])

            g = self.tilt.read()
            if g:
                print("GESTURE:", g)

                # Correct move
                if g == move:
                    earned = BASE_SCORE_PER_LEVEL + d["score_bonus"]
                    self.score += earned
                    print("SUCCESS +", earned)
                    self.px(GOOD)
                    tone(self.piezo,900,0.1)
                    return True

                # Wrong gesture
                else:
                    print("WRONG")
                    self.px(BAD)
                    tone(self.piezo,200,0.3)
                    return False

            time.sleep(0.02)

    # ----------------------------------------------------------------------
    # Main Loop
    # ----------------------------------------------------------------------
    def run(self):
        self.score=0
        while True:
            self.px(FLYING)

            # ==== Difficulty selection ====
            self.select_difficulty()

            self.disp.show("STAR RUN","","Rotate to Start","")
            self.wait_for_rotate()

            # ==== Play levels ====
            won=True
            for lvl in range(1, MAX_LEVELS+1):
                if not self.play_level(lvl):
                    won=False
                    break

            # ==== END SCREENS (extended duration) ====
            if won:
                self.px(WIN)
                self.disp.show("YOU WIN!", f"Score:{self.score}", "", "Rotate to restart")
                tone(self.piezo,523,0.1); time.sleep(0.05)
                tone(self.piezo,659,0.1); time.sleep(0.05)
                tone(self.piezo,784,0.2)

                time.sleep(self.END_SCREEN_DELAY)  # ← NEW 3s pause

            else:
                self.px(BAD)
                self.disp.show("GAME OVER", f"Score:{self.score}", "", "Rotate to retry")
                tone(self.piezo,200,0.3)
                self.score = 0

                time.sleep(self.END_SCREEN_DELAY)  # ← NEW 3s pause

            # After waiting, allow restart
            self.wait_for_rotate()

# ============================================================================
# MAIN ENTRY
# ============================================================================
if __name__=="__main__":
    game = StarRun()
    game.run()
