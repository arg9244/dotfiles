### How to Edit Keybinds

Currently, **custom keybindings are not natively supported** in `bottom`. This feature is tracked in [GitHub Issue #454](https://github.com/ClementTsang/bottom/issues/454) and is currently at 0% completion for the "Custom keybindings" milestone.

However, you have two options to "edit" the behavior:

1.  **Disable All Keybinds:**
    You can disable all keyboard shortcuts entirely. This is useful if you want to use `bottom` purely as a display or if you are using an external tool to handle inputs.
    *   **Via Config File:** Open your `bottom.toml` configuration file and set:
        ```toml
        # Disable keyboard shortcuts
        disable_keys = true
        ```
        *   **Linux/macOS:** `~/.config/bottom/bottom.toml`
        *   **Windows:** `%APPDATA%\bottom\bottom.toml`
    *   **Via CLI Flag:** Run the application with `btm --disable_keys`.

2.  **OS-Level Remapping (Workaround):**
    Since `bottom` does not support remapping internally, you must use system-level tools to map your desired keys to the default `bottom` keys.
    *   **Linux:** Use `xmodmap`, `sxhkd`, or ` interception tools`.
    *   **macOS:** Use **Karabiner-Elements**.
    *   **Windows:** Use **AutoHotKey** or **PowerToys**.

---

### Default Keybinds

You can always view these in-app by pressing `?`. Note that keybindings are generally **case-sensitive**.

#### 1. Global / Navigation
| Key(s) | Action |
| :--- | :--- |
| `q`, `Ctrl` + `c` | Quit |
| `Esc` | Close dialog windows, search, widgets, or exit expanded mode |
| `Ctrl` + `r` | Reset display and any collected data |
| `f` | Freeze/unfreeze updating with new data |
| `?` | Open help menu |
| `e` | Toggle expanding the currently selected widget |
| **Widget Selection** | |
| `Ctrl` + `Up` / `Shift` + `Up` / `K` / `W` | Select the widget above |
| `Ctrl` + `Down` / `Shift` + `Down` / `J` / `S` | Select the widget below |
| `Ctrl` + `Left` / `Shift` + `Left` / `H` / `A` | Select the widget on the left |
| `Ctrl` + `Right` / `Shift` + `Right` / `L` / `D` | Select the widget on the right |
| **Navigation within Widgets** | |
| `Up`, `k` | Move up |
| `Down`, `j` | Move down |
| `Left`, `h`, `Alt` + `h` | Move left |
| `Right`, `l`, `Alt` + `l` | Move right |
| `g` + `g`, `Home` | Jump to the first entry |
| `G`, `End` | Jump to the last entry |
| `Page Up`, `Page Down` | Scroll up/down by a page |
| `Ctrl` + `u` | Scroll up by half a page |
| `Ctrl` + `d` | Scroll down by half a page |

#### 2. Process Widget
| Key(s) | Action |
| :--- | :--- |
| `d` + `d`, `F9` | Send a kill signal to the selected process |
| `c` | Sort by CPU usage (press again to reverse) |
| `m` | Sort by memory usage (press again to reverse) |
| `p` | Sort by PID (press again to reverse) |
| `n` | Sort by process name (press again to reverse) |
| `M` | Sort by GPU memory usage (press again to reverse) |
| `C` | Sort by GPU usage (press again to reverse) |
| `Tab` | Toggle grouping processes with the same name |
| `P` | Toggle full command vs. process name |
| `t`, `F5` | Toggle tree mode |
| `z` | Toggle hiding of kernel threads |
| `I` | Invert current sort |
| `%` | Toggle values vs. percentages for memory |
| **Search & Sort** | |
| `Ctrl` + `f`, `/` | Open search widget |
| `s`, `F6`, `Del` | Open sort widget |
| `Esc` | Close search/sort widget |
| `Enter` | Apply sort (in sort widget) |
| `Alt` + `c` (F1) | Toggle case sensitivity (in search) |
| `Alt` + `w` (F2) | Toggle whole word matching (in search) |
| `Alt` + `r` (F3) | Toggle regex (in search) |

#### 3. Disk Widget
| Key(s) | Action |
| :--- | :--- |
| `d` | Sort by disk name |
| `m` | Sort by mount point |
| `u` | Sort by amount used |
| `n` | Sort by amount free |
| `t` | Sort by total space |
| `p` | Sort by percentage used |
| `r` | Sort by read rate |
| `w` | Sort by write rate |

#### 4. Temperature Widget
| Key(s) | Action |
| :--- | :--- |
| `t` | Sort by temperature |
| `s` | Sort by sensor name |

#### 5. Battery Widget
| Key(s) | Action |
| :--- | :--- |
| `Left`, `h`, `Alt` + `h` | Move to battery entry on the left |
| `Right`, `l`, `Alt` + `l` | Move to battery entry on the right |

#### 6. Graph Widgets (CPU, Memory, Network)
| Key(s) | Action |
| :--- | :--- |
| `+` | Zoom in (decrease time range) |
| `-` | Zoom out (increase time range) |
| `=` | Reset zoom |
| **CPU Legend** | |
| `Up` / `k` | Move up in legend |
| `Down` / `j` | Move down in legend |
| `g` + `g` / `Home` | Jump to top of legend |
| `G` / `End` | Jump to bottom of legend |

#### 7. Mouse Bindings
| Action | Result |
| :--- | :--- |
| **Left Click** | Selects a widget or an entry in a table. |
| **Scroll Wheel** | Zooms in/out on graphs (CPU, Memory, Network). |
| **Click Header** | Sorts the table by that column (Process/Disk/Temperature). |

*Note: In **Basic Mode**, widget expansion (`e`) is disabled, and the `%` key toggles total usage vs. percentage for the Memory widget specifically.*
