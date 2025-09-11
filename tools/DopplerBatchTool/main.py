import tkinter as tk
from controller import Controller

if __name__ == "__main__":
    root = tk.Tk()
    app = Controller(root)
    root.mainloop()