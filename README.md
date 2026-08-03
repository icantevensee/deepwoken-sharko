
### This is the experimental branch for the sharko. The latest developments on the application will be pushed here.

### For information on how to use, refer to the main branch.

### Progress:
- **Code Organization**: Code has been split into files containing their own objects, and a singular type convention has been applied.
- **New boss fight**: New boss fight that can be acessed with the fight option. This is what the majority of the code is about, but it doesn't affect performance for the base features.
- **General improvements**: Made improvements such as stopping clipping for the death animation particles and optimizing some parts of code.
- **Migrated to PyQt6**: Previously this was a Tkinter application, now it's written in PyQt6, letting it make use of all qt features.

### ToDo here in Experimental content before we can merge to main:
- **Zero memory leaks**: I have fixed all memory leaks save for one where if fight mode is repeadedly toggled, it accumulates.
- **Zero bugs**: Insallah we will get these bugs fixed.
- **Code organization**: Although I have made great progress towards organizing the code from the one-file sharko script, it's still not organized enough to be easy to understand.
- **Boss battle finished**: Voice acting + more attacks.

<img src="/img/5.gif" width="400">

### Usage:
1. **Python Installation**: If you have Python installed, follow these steps:
    - Clone the repository to your local machine.
    - Ensure you have Python installed along with the required libraries (Pyqt5, Pygame, pillow, ctypes, pynput, random, etc).
    - Run the main Python script to launch the Sharko application.
    - Interact with the Sharko by clicking on the interface and observing its various animations and sounds.

### Download:
[Download ZIP](https://github.com/icantevensee/deepwoken-sharko/archive/refs/heads/Stable_Experimental_Content.zip)

<img src="/img/2.png" width="400">




*Note: Ensure that image and sound files are correctly referenced in the code for proper functionality. If you have any questions, problems, or suggestions, please contact Alexander-Of-Macedon using the email listed on their github profile.*


