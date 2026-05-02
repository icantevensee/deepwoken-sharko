"""
Constants and Configuration Module

Centralized configuration for the Sharko game including:
- Animation and timing parameters
- File paths for assets, images, and sounds
- Combat mechanics settings (parry window, cooldowns)
- UI parameters and text rendering settings
- Windows API constants
"""

def _decode_escapes(s):
    """Decode escape sequences and HTML entities in strings"""
    if not isinstance(s, str):
        return s
    if ('\\u' in s) or ('\\x' in s) or ('\\U' in s) or ('&#' in s) or ('&' in s):
        try:
            decoded = s.encode('utf-8').decode('unicode_escape')
        except Exception:
            decoded = s
        try:
            import html
            decoded = html.unescape(decoded)
        except Exception:
            pass
        return decoded
    return s

class SharkoConstants:
    """Global constants and configuration for the Sharko game."""
    
    # Animation/timing
    FADE_STEP                   = 1
    ANIMATION_DELAY             = 500
    TALKING_ANIMATION_DELAY     = 10000
    IDLE_ANIMATION_DELAY        = 20000
    GREETING_ANIMATION_DELAY    = 8000
    REMOVAL_ANIMATION_DELAY     = 3800
    INACTIVE_TIME_REQUIREMENT   = 60
    
    # Window
    WINDOW_SIZE                 = "357x342"
    
    # Paths
    ASSETS_PATH                 = "assets/"
    CURRENT_IMAGES_PATH         = "assets/sharko/"
    IMAGES_PATH                 = "assets/sharko/"
    BAR_IMG_PATH                = "assets/UI/boss_bar_border.png"
    MARKER_PATH                 = "assets/UI/boss_bar_pins.png"
    CENTER_ICON_PATH            = "assets/UI/boss_bar_skull.png"
    FONT_PATH                   = "assets/fonts/Boss_Font.otf"
    TALKING_SENTENCES_PATH      = "assets/sentences/talking/"
    GREETING_SENTENCES_PATH     = "assets/sentences/greeting/"
    REMOVAL_SENTENCES_PATH      = "assets/sentences/removal/"
    
    # Sounds
    END_TALKING_SOUND           = "assets/sounds/end_talking.mp3"
    START_TALKING_SOUND         = "assets/sounds/start_talking.mp3"
    CLASH_SOUND                 = "assets/sounds/Clash.mp3"
    GREETING_SOUND              = "assets/sounds/greeting.mp3"
    ANSWER_SOUND                = "assets/sounds/answer_question.mp3"
    
    # Fight SFX sounds
    BLOCK_ATTEMPT_SOUND         = "assets/sounds/fight-sfx/Block_Attempt.mp3"
    PARRY_SOUND                 = "assets/sounds/fight-sfx/Parry.mp3"
    BLOCK_SOUND                 = "assets/sounds/fight-sfx/Block.mp3"
    HIT_SOUND                   = "assets/sounds/fight-sfx/Hit.mp3"

    # Fonts
    FONT = r"assets/fonts/TheFont.ttf"
    
    # COM interfaces
    CLSID_ShellWindows      = "{9BA05972-F6A8-11CF-A442-00A0C90A8F39}"
    IID_IFolderView         = "{CDE725B0-CCC9-4519-917E-325D72FAB4CE}"
    
    # Windows API constants
    SWC_DESKTOP             = 0x08
    SWFO_NEEDDISPATCH       = 0x01
    SPI_GETWORKAREA         = 0x0030
    LVM_SETITEMPOSITION     = 0x100F
    LVM_GETITEMCOUNT        = 0x1004
    LVM_GETITEMW            = 0x1000 + 75
    LVIF_TEXT               = 0x0001
    LVM_GETITEMTEXTW        = 0x1000 + 115
    
    # Movement & Physics
    WALKSPEED = 230  # Pixels per second
    
    # Audio
    MIN_VOLUME = 0.1
    
    # Combat Mechanics
    PARRY_WINDOW            = 0.3  # seconds
    PARRY_BLOCK_COOLDOWN    = 0.75  # seconds
    ATTACL_WINDOW            = 0.3  # seconds
    ATTACK_COOLDOWN    = 0.75  # seconds
    
    # UI & Text Rendering
    SPRITE_WIDTH = 165
    SPRITE_HEIGHT = 165
    QUESTION_BOX_WIDTH          = 255
    QUESTION_BOX_HEIGHT         = 140
    QUESTION_BOX_TOP_Y          = 9
    QUESTION_BOX_OPTION1_Y      = 96
    QUESTION_BOX_OPTION2_Y      = 126
    QUESTION_BOX_OPTION_HEIGHT  = 30
    QUESTION_TEXT_HEIGHT        = 80
    TEXT_RENDER_PADDING         = 0
    TEXT_LINE_SPACING           = 8
    FONT_SIZE_MAX               = 72
    FONT_SIZE_MIN               = 8
    FRAME_DELAY_MS              = 16  # Milliseconds between animation frames


    try:
        file = open('Lines.txt', 'r', encoding='utf-8')
        Lines = file.readlines()
        clean_lines = [_decode_escapes(line.strip()) for line in Lines]
        Lines = clean_lines
    except Exception:
        try:
            file = open('Lines.txt', 'r')
            Lines = [line.strip() for line in file.readlines()]
        except Exception:
            Lines = []
    finally:
        try:
            file.close()
        except Exception:
            pass
    file = open('removal_lines+intro_line.txt', 'r', encoding='utf-8')
    removal_intro_lines = file.readlines()
    removal_lines = []

    for index, line in enumerate(removal_intro_lines):
        decoded = _decode_escapes(line.strip())
        if index > 2:
            removal_lines.append(decoded)
        elif index == 1:
            intro_line = decoded
    file.close()

    file = open('Questions.txt', 'r', encoding='utf-8')
    removal_intro_lines = file.readlines()
    Questions = []
    for index, line in enumerate(removal_intro_lines):
        decoded = _decode_escapes(line.strip())
        current_question = int(index/5)
        current_line  = index - current_question*5
        if current_line == 0:
            Questions.append([])
        Questions[current_question].append(decoded)
    file.close()