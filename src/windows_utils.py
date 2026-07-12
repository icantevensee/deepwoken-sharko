"""
Desktop Utilities Module

Provides Windows desktop manipulation utilities for:
- Desktop interface access via COM
- Icon position management
- Window handle operations
- Desktop property queries and modifications
"""

import ctypes
import os
import time
import pythoncom

import win32com.client as   wcomcli
import                      win32con
import                      win32gui
import                      win32process
import                      winreg
import                      winshell
from win32com.client import Dispatch
from win32com.shell  import shell, shellcon  # type: ignore

from constants import SharkoConstants

_cached_desktop_hwnds = set()


class WindowsUtils:
    """Utilities for desktop icon manipulation and window management."""

    @staticmethod
    def clamp(v, lo, hi):
        """Clamp value between lo and hi bounds."""
        return max(lo, min(hi, v))

    @staticmethod
    def disable_desktop_grid_and_autoarrange_universal():

        desktop_shell_view = [0]

        def enum_windows_callback(hwnd, extra):
            shell_view = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
            if shell_view != 0:
                desktop_shell_view[0] = shell_view
                return False
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        shell_view = desktop_shell_view[0]

        if shell_view == 0:
            print("Could not find the Desktop window structure.")
            return

        list_view = win32gui.FindWindowEx(shell_view, 0, "SysListView32", None)

        if list_view == 0:
            print("Could not find the Desktop icon list view control.")
            return

        LVS_AUTOARRANGE = 0x0100
        current_style = win32gui.GetWindowLong(list_view, win32con.GWL_STYLE)
        new_style = current_style & ~LVS_AUTOARRANGE
        win32gui.SetWindowLong(list_view, win32con.GWL_STYLE, new_style)

        current_ext_style = win32gui.SendMessage(list_view, SharkoConstants.LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0)

        new_ext_style = current_ext_style & ~SharkoConstants.LVS_EX_SNAPTOGRID

        win32gui.SendMessage(
            list_view,
            SharkoConstants.LVM_SETEXTENDEDLISTVIEWSTYLE,
            SharkoConstants.LVS_EX_SNAPTOGRID,
            new_ext_style,
        )

        win32gui.RedrawWindow(
            list_view,
            None,
            None,
            win32con.RDW_INVALIDATE
            | win32con.RDW_UPDATENOW
            | win32con.RDW_ERASE
            | win32con.RDW_FRAME,
        )

    @staticmethod
    def cache_desktop_handles():
        """Maps out the workspace wallpaper window handles cleanly."""
        global _cached_desktop_hwnds
        _cached_desktop_hwnds.clear()

        progman = win32gui.FindWindow("Progman", "Program Manager")
        if progman:
            _cached_desktop_hwnds.add(progman)
            shelldll = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)
            if shelldll:
                _cached_desktop_hwnds.add(shelldll)

        def callback(hwnd, extra):
            if win32gui.GetClassName(hwnd) == "WorkerW":
                child = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
                if child:
                    _cached_desktop_hwnds.add(hwnd)
                    _cached_desktop_hwnds.add(child)
            return True
        win32gui.EnumWindows(callback, None)

    @staticmethod
    def should_supress_click():
        cursor_pos = win32gui.GetCursorPos()
        hwnd_under_cursor = win32gui.WindowFromPoint(cursor_pos)

        current = hwnd_under_cursor
        is_desktop = False
        while current:
            if current in _cached_desktop_hwnds:
                is_desktop = True
                break
            current = win32gui.GetParent(current)

        return is_desktop

    @staticmethod
    def are_notifications_enabled():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SharkoConstants.PUSH_NOTIFICATIONS_REG_PATH) as key:
                value, _ = winreg.QueryValueEx(key, "ToastEnabled")
                return value == 1
        except FileNotFoundError:
            return True
        except Exception as e:
            print(f"Error checking master notification switch: {e}")
            return False

    @staticmethod
    def get_work_area_height():
        desktop_working_area = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SharkoConstants.SPI_GETWORKAREA, 0, ctypes.byref(desktop_working_area), 0)
        return desktop_working_area.bottom - desktop_working_area.top

    @staticmethod
    def icon_exists(hwnd_lv, index, lvm_getitemcount=0x1004):
        """Check if a desktop icon exists at the given index."""
        count = win32gui.SendMessage(hwnd_lv, lvm_getitemcount, 0, 0)
        return 0 <= index < count

    @staticmethod
    def get_desktop_interfaces(clsid_shell_windows, iid_ifolderview, swc_desktop, swfo_needdispatch):
        """Get desktop folder view interface and list view window handle via COM."""
        shell_windows = wcomcli.Dispatch(clsid_shell_windows)
        hwnd = 0

        dispatch = shell_windows.FindWindowSW(
            wcomcli.VARIANT(pythoncom.VT_I4, shellcon.CSIDL_DESKTOP),
            wcomcli.VARIANT(pythoncom.VT_EMPTY, None),
            swc_desktop,
            hwnd,
            swfo_needdispatch,
        )

        service_provider = dispatch._oleobj_.QueryInterface(
            pythoncom.IID_IServiceProvider
        )

        browser = service_provider.QueryService(
            shell.SID_STopLevelBrowser,
            shell.IID_IShellBrowser,
        )

        shell_view = browser.QueryActiveShellView()
        folder_view = shell_view.QueryInterface(iid_ifolderview)

        progman = win32gui.FindWindow("Progman", "Program Manager")
        shell_dll = win32gui.FindWindowEx(progman, 0, "SHELLDLL_DefView", None)
        hwnd_lv = win32gui.FindWindowEx(shell_dll, 0, "SysListView32", None)

        return folder_view, hwnd_lv

    @staticmethod
    def get_item_text(hwnd, index):
        """Retrieve the text label of a desktop icon by reading remote process memory."""

        class LVITEMW(ctypes.Structure):
            _fields_ = [
                ("mask", ctypes.wintypes.UINT),
                ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int),
                ("state", ctypes.wintypes.UINT),
                ("stateMask", ctypes.wintypes.UINT),
                ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int),
                ("lParam", ctypes.wintypes.LPARAM),
                ("iIndent", ctypes.c_int),
                ("iGroupId", ctypes.c_int),
                ("cColumns", ctypes.wintypes.UINT),
                ("puColumns", ctypes.c_void_p),
                ("piColFmt", ctypes.c_void_p),
                ("iGroup", ctypes.c_int),
            ]

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_handle = ctypes.windll.kernel32.OpenProcess(0x38, False, pid)
        if not process_handle:
            return ""

        try:
            buf_size = 512
            remote_mem = ctypes.windll.kernel32.VirtualAllocEx(
                process_handle, None, buf_size, 0x1000, 0x04
            )
            text_addr = remote_mem + ctypes.sizeof(LVITEMW)
            item = LVITEMW(
                mask=1,
                iItem=index,
                pszText=text_addr,
                cchTextMax=(buf_size - ctypes.sizeof(LVITEMW)) // 2,
            )
            ctypes.windll.kernel32.WriteProcessMemory(
                process_handle,
                remote_mem,
                ctypes.byref(item),
                ctypes.sizeof(item),
                None,
            )
            win32gui.SendMessage(
                hwnd, SharkoConstants.LVM_GETITEMTEXTW, index, remote_mem
            )
            res_buf = ctypes.create_unicode_buffer(item.cchTextMax)
            ctypes.windll.kernel32.ReadProcessMemory(
                process_handle, text_addr, res_buf, ctypes.sizeof(res_buf), None
            )
            ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_mem, 0, 0x8000)
            return res_buf.value
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)

    @staticmethod
    def get_actual_index(hwnd_lv, target_name):
        """Find the actual index of a desktop icon by name"""

        class LVITEMW(ctypes.Structure):
            _fields_ = [
                ("mask", ctypes.wintypes.UINT),
                ("iItem", ctypes.c_int),
                ("iSubItem", ctypes.c_int),
                ("state", ctypes.wintypes.UINT),
                ("stateMask", ctypes.wintypes.UINT),
                ("pszText", ctypes.c_void_p),
                ("cchTextMax", ctypes.c_int),
                ("iImage", ctypes.c_int),
                ("lParam", ctypes.wintypes.LPARAM),
            ]

        search_str = target_name.split(".lnk")[0]
        _, pid = win32process.GetWindowThreadProcessId(hwnd_lv)
        process_handle = ctypes.windll.kernel32.OpenProcess(0x38, False, pid)

        if not process_handle:
            return -1

        try:
            item_count = win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0)
            remote_mem = ctypes.windll.kernel32.VirtualAllocEx(process_handle, None, 1024, 0x1000, 0x04)
            struct_addr = remote_mem
            text_buffer_addr = remote_mem + ctypes.sizeof(LVITEMW)

            for i in range(item_count):
                lv_item = LVITEMW()
                lv_item.mask = SharkoConstants.LVIF_TEXT
                lv_item.iItem = i
                lv_item.iSubItem = 0
                lv_item.pszText = text_buffer_addr
                lv_item.cchTextMax = 260

                ctypes.windll.kernel32.WriteProcessMemory(
                    process_handle,
                    struct_addr,
                    ctypes.byref(lv_item),
                    ctypes.sizeof(lv_item),
                    None,
                )
                win32gui.SendMessage(
                    hwnd_lv, SharkoConstants.LVM_GETITEMW, i, struct_addr
                )

                name_buf = ctypes.create_unicode_buffer(260)
                ctypes.windll.kernel32.ReadProcessMemory(
                    process_handle,
                    text_buffer_addr,
                    name_buf,
                    ctypes.sizeof(name_buf),
                    None,
                )

                if name_buf.value == search_str:
                    ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_mem, 0, 0x8000)
                    return i

            ctypes.windll.kernel32.VirtualFreeEx(process_handle, remote_mem, 0, 0x8000)
            return -1
        finally:
            ctypes.windll.kernel32.CloseHandle(process_handle)

    @staticmethod
    def create_shortcut(hwnd_lv, base_path="assets/"):
        """Create a new desktop shortcut"""
        desktop = winshell.desktop()
        base_name = "Destroyman III"
        extension = ".lnk"

        path = os.path.join(desktop, f"{base_name}{extension}")
        counter = 1

        while os.path.exists(path):
            unique_name = f"{base_name} ({counter}){extension}"
            path = os.path.join(desktop, unique_name)
            counter += 1

        target = r"C:\Windows\System32\cmd.exe"
        icon_path = os.path.abspath(os.path.join(base_path, "sharko.ico"))

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(path)

        shortcut.Targetpath = target
        shortcut.WorkingDirectory = os.path.dirname(target)

        if os.path.exists(icon_path):
            shortcut.IconLocation = icon_path

        shortcut.save()

        name_str = f"{base_name}" if counter == 1 else f"{base_name} ({counter - 1})"
        start_time = time.time()

        while time.time() - start_time < 200:
            idx = WindowsUtils.get_actual_index(hwnd_lv, name_str)
            if idx != -1:
                confirmed_text = WindowsUtils.get_item_text(hwnd_lv, idx)
                if confirmed_text == name_str and WindowsUtils.icon_exists(hwnd_lv, idx):
                    return idx
            time.sleep(0.1)

        print("Failed to find shortcut before timeout, defaulting to last index.")
        return win32gui.SendMessage(hwnd_lv, SharkoConstants.LVM_GETITEMCOUNT, 0, 0) - 1
