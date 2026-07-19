"""
Constants and Configuration Module

Centralized configuration for the Sharko game including:
- Animation and timing parameters
- File paths for assets, images, and sounds
- Combat mechanics settings (parry window, cooldowns)
- UI parameters and text rendering settings
- Windows API constants
"""

import html


def _decode_escapes(s):
    """Decode escape sequences and HTML entities in strings"""
    if not isinstance(s, str):
        return s
    if ("\\u" in s) or ("\\x" in s) or ("\\U" in s) or ("&#" in s) or ("&" in s):
        try:
            decoded = s.encode("utf-8").decode("unicode_escape")
        except Exception:
            decoded = s
        try:
            decoded = html.unescape(decoded)
        except Exception:
            pass
        return decoded
    return s


class SharkoConstants:
    """Global constants and configuration for the Sharko game."""

    # Debug Mode Flag - todo: visualizes ram and cpu over time in seperate window + currently alive large objects, Catch the tiny memory leaks.
    DEBUG = False

    # Animation/timing
    FADE_STEP                   = 1
    ANIMATION_DELAY             = 500
    TALKING_ANIMATION_DELAY     = 10000
    IDLE_ANIMATION_DELAY        = 20000
    GREETING_ANIMATION_DELAY    = 8000
    REMOVAL_ANIMATION_DELAY     = 3800
    INACTIVE_TIME_REQUIREMENT   = 60000
    INTER_ATTACK_IDLE_TIME      = 1000

    # Window
    WINDOW_SIZE_X               = 357
    WINDOW_SIZE_Y               = 342

    ROAR_MOUTH_OFFSET_Y         = 277
    ROAR_MOUTH_OFFSET_X_RIGHT   = 250

    FALLING_SHARKO_SIZE_X       = 696
    FALLING_SHARKO_SIZE_Y       = 772

    TEXT_OFFSET_LEFT            = 97
    TEXT_OFFSET_RIGHT           = 9

    # General paths
    CURRENT_IMAGES_PATH         = "assets/sharko/"
    IMAGES_PATH                 = "assets/sharko/"
    TALKING_SENTENCES_PATH      = "assets/sentences/talking/"
    GREETING_SENTENCES_PATH     = "assets/sentences/greeting/"
    REMOVAL_SENTENCES_PATH      = "assets/sentences/removal/"

    # Bar paths
    BOSS_BAR_IMG_PATH           = "assets/UI/boss_bar_border.png"
    POSTURE_BAR_BORDER_PATH     = "assets/UI/posture_bar_border.png"
    PLR_HEALTH_BAR_BORDER_PATH  = "assets/UI/player_health_bar_border.png"
    SIDEBAR_BORDER_PATH         = "assets/UI/sidebar_border.png"
    BOSS_BAR_PINS_PATH          = "assets/UI/boss_bar_pins.png"
    POSTURE_BAR_PINS_PATH       = "assets/UI/posture_bar_pins.png"
    PLR_HEALTH_BAR_PINS_PATH    = "assets/UI/player_health_bar_pins.png"
    BOSS_BAR_SKULL_PATH         = "assets/UI/boss_bar_skull.png"
    PARRY_OVERLAY_PATH          = "assets/UI/parry_overlay.png"
    PARRY_COOLDOWN_ICON_PATH    = "assets/UI/boss_bar_skull.png"
    ICON_FRAME_PATH             = "assets/UI/parry_overlay.png"

    # Themes
    THEME_VAMP                  = "assets/sounds/boss-phase-music/Theme_Vamp.mp3"
    THEME_LOOP                  = "assets/sounds/boss-phase-music/Theme_Loop.mp3"

    # Sounds
    END_TALKING_SOUND           = "assets/sounds/end_talking.mp3"
    START_TALKING_SOUND         = "assets/sounds/start_talking.mp3"
    CLASH_SOUND                 = "assets/sounds/Clash.mp3"
    GREETING_SOUND              = "assets/sounds/greeting.mp3"
    ANSWER_SOUND                = "assets/sounds/answer_question.mp3"

    # Combat sfx
    BLOCK_ATTEMPT_SOUND         = "assets/sounds/fight-sfx/Block_Attempt.mp3"
    PARRY_SOUND                 = "assets/sounds/fight-sfx/Parry.mp3"
    BLOCK_SOUND                 = "assets/sounds/fight-sfx/Block.mp3"
    HIT_SOUND                   = "assets/sounds/fight-sfx/Hit.mp3"

    # fight sfx
    LONG_ROAR_SOUND             = "assets/sounds/fight-sfx/Long_Roar1.mp3"
    ROAR_SOUND_1                = "assets/sounds/fight-sfx/Roar1.mp3"
    ROAR_SOUND_2                = "assets/sounds/fight-sfx/Roar2.mp3"
    DREAD_BREATH_SOUND          = "assets/sounds/fight-sfx/Breath.mp3"

    # Fight constants
    MAX_BOSS_HEALTH             = 2000
    MAX_PLAYER_HEALTH           = 500
    MAX_POSTURE                 = 20
    POSTURE_PARRY_COST          = 4
    POSTURE_BREAK_COOLDOWN      = 3
    M1_DAMAGE                   = 30

    LAZER_WINDUP                = 750

    # Attack statistics
    ATTACK_STATS = {
        "icon_attack": {"damage": 20, "posture": 3},
        "toast_attack": {"damage": 40, "posture": 5},
        "falling_sharko": {"damage": 100, "posture": 15},
        "jump": {"damage": 20, "posture": 2},
        "single_lazer_hit": {"damage": 5, "posture": 1},
        "sword_slash": {"damage": 25, "posture": 3},
    }

    # Fonts
    SPEECH_FONT             = "assets/fonts/TheFont.ttf"
    BOSS_FONT               = "assets/fonts/Boss_Font.otf"

    # COM interfaces
    CLSID_ShellWindows      = "{9BA05972-F6A8-11CF-A442-00A0C90A8F39}"
    IID_IFolderView         = "{CDE725B0-CCC9-4519-917E-325D72FAB4CE}"

    # Windows API constants
    LVS_EX_SNAPTOGRID       = 0x00080000
    WDA_EXCLUDEFROMCAPTURE  = 0x00000011
    SWC_DESKTOP             = 0x08
    SWFO_NEEDDISPATCH       = 0x01
    COINIT_APARTMENTTHREADED = 0x2
    SPI_GETWORKAREA         = 0x0030
    LVM_SETITEMPOSITION     = 0x100F
    LVM_GETITEMCOUNT        = 0x1004
    LVM_GETITEMW            = 0x1000 + 75
    LVM_GETITEMSPACING      = 0x1033
    LVIF_TEXT               = 0x0001
    LVM_GETITEMTEXTW        = 0x1000 + 115
    LVM_FIRST               = 0x1000
    LVM_GETEXTENDEDLISTVIEWSTYLE = LVM_FIRST + 55
    LVM_SETEXTENDEDLISTVIEWSTYLE = LVM_FIRST + 54
    SUPRESS_DESKTOP_MENU_TIMER_ID = 1

    # Windows Registry Paths
    PUSH_NOTIFICATIONS_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\PushNotifications"

    # Movement & Physics
    WALKSPEED = 230  # Pixels per second

    # Combat Mechanics
    PARRY_WINDOW            = 0.3  # seconds
    PARRY_BLOCK_COOLDOWN    = 0.75
    ATTACK_COOLDOWN    = 0.75

    # UI & Text Rendering
    SPRITE_WIDTH = 165
    SPRITE_HEIGHT = 165
    QUESTION_BOX_WIDTH          = 250
    QUESTION_BOX_HEIGHT         = 150
    QUESTION_BOX_TOP_Y          = 9
    QUESTION_BOX_OPTION1_Y      = 90
    QUESTION_BOX_OPTION2_Y      = 120
    QUESTION_BOX_OPTION_HEIGHT  = 40
    QUESTION_TEXT_HEIGHT        = 80
    TEXT_RENDER_PADDING         = 3
    TEXT_LINE_SPACING           = 3
    FONT_SIZE_MAX               = 80
    FONT_SIZE_MIN               = 5
    FRAME_DELAY_MS              = 16  # Milliseconds between animation frames

    TOAST_TEXT = {
        "titles": ["Attack!", "Destroy!"],
        "descriptions": ["ROARRRRRRRRRR", "Block parry dodge", "Thy end is now!"]
    }

    try:
        file = open("Lines.txt", "r", encoding="utf-8")
        Lines = file.readlines()
        clean_lines = [_decode_escapes(line.strip()) for line in Lines]
        Lines = clean_lines
    except Exception:
        try:
            file = open("Lines.txt", "r")
            Lines = [line.strip() for line in file.readlines()]
        except Exception:
            Lines = []
    finally:
        try:
            file.close()
        except Exception:
            pass
    file = open("removal_lines+intro_line.txt", "r", encoding="utf-8")
    removal_intro_lines = file.readlines()
    removal_lines = []

    for index, line in enumerate(removal_intro_lines):
        decoded = _decode_escapes(line.strip())
        if index > 2:
            removal_lines.append(decoded)
        elif index == 1:
            intro_line = decoded
    file.close()

    file = open("Questions.txt", "r", encoding="utf-8")
    question_lines = file.readlines()
    Questions = []
    for index, line in enumerate(question_lines):
        decoded = _decode_escapes(line.strip())
        current_question = int(index / 5)
        current_line  = index - current_question * 5
        if current_line == 0:
            Questions.append([])
        Questions[current_question].append(decoded)
    file.close()
