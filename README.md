
### This is the experimental branch for the sharko. The latest developments on the program will be pushed here.

### For information on how to use, refer to the main branch.

### Progress:
- **Code Organization**: Code has been split into multiple files, and a singlular type convention has been applied. I've also organized a bunch. There's still a little bit of work that needs to be done though
- **New boss fight**: New boss fight that can be acessed with the fight option, so far there has been: A boss bar, jump attack, jump and hit desktop shortcut at mouse, and lazer attack added.
- **General improvements**: Made improvements such as making the death animation particles not be cut off and optimizing some parts of code.
- **Migrated to PyQt5**: Previously this was a Tkinter application, now it's 100% PyQt5, which means it's more optimizaed and it has a cooler, customized menu system.

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


<img src="/img/2.png" width="400">




*Note: Ensure that image and sound files are correctly referenced in the code for proper functionality. If you have any questions, problems, or suggestions, please contact Alexander-Of-Macedon using the email listed on their github profile.*


