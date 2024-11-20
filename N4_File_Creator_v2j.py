import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.font import BOLD
import os
import pandas as pd
import numpy as np
from pathlib import Path
import math
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import yaml
import json
from enum import Enum
from collections import defaultdict, Counter
from datetime import datetime
import time
#from Neoden4_PCR_Splitter import PCR_File_Splitter
#from Assembly_file_splitter import AssemblyFileSplitter
from typing import Dict, List, Tuple, Optional, Callable  # Add Callable here

FEEDER_20_MAX_COUNT = 4  # Define at class level

class PlacementResult(Enum):
    PLACED = 1
    ALREADY_PLACED = 2
    NOT_PLACED = 3

# ---- Custom Exceptions ----
class PCBProcessingError(Exception):
    """Custom exception for PCB processing errors"""
    pass

# ---- Data Models ----
@dataclass
class Point:
    x: float
    y: float
    
    def distance_to(self, other: 'Point') -> float:
        return np.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

@dataclass
class Component:
    refdes: str
    value: str
    symbol: str
    position: Point
    rotation: float
    mirror: bool
    feeder_id: Optional[str] = None
    nozzle_type: Optional[str] = None
    
    @property
    def is_fiducial(self) -> bool:
        return self.refdes.startswith('FID')

# ---- Configuration Management ----
@dataclass
class PCBConfig:
    default_path: str
    fiducial_prefix: str
    default_pcb_width: float
    nozzle_types: List[str]
    feeder_types: List[str]
    
    @classmethod
    def load_from_file(cls, config_path: str) -> 'PCBConfig':
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            return cls(**config_data)
        except Exception as e:
            # Fallback to default config if file loading fails
            return cls(
                default_path="Z:/Users/godwinm.mayers/Neoden4Assembly/PCB_Assembly/",
                fiducial_prefix="FID",
                default_pcb_width=0.0,
                nozzle_types=["1", "2", "3", "4"],
                feeder_types=["comp", "stack", "mark"]
            )

# ---- Progress Tracking ----
class ProgressTracker:
    def __init__(self, parent_widget: tk.Widget):
        self.progress_frame = tk.Frame(parent_widget)
        self.progress_frame.grid(row=8, column=0, columnspan=4, pady=5)
        
        # Progress bar on first row
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            length=200,
            mode='determinate'
        )
        self.progress_bar.grid(row=0, column=0, columnspan=2, padx=5)
        
        # Status label on second row
        self.progress_label = tk.Label(self.progress_frame, text="")
        self.progress_label.grid(row=1, column=0, columnspan=2, padx=5, pady=(2, 0))  # Small top padding between bar and text
    
    def update_progress(self, current: int, total: int, status: str) -> None:
        percentage = (current / total) * 100
        self.progress_bar['value'] = percentage
        self.progress_label.config(text=f"{status}: {percentage:.1f}%")
        self.progress_frame.update_idletasks()

# ---- Main Application ----
class N4SortGUIApp(tk.Tk):
    def __init__(self, title: str, size: Tuple[int, int]):
        super().__init__()
        
        # Initialize configuration
        self.config = PCBConfig.load_from_file("config.json")
        
        # Setup logging
        self.setup_logging()
        
        # Setup GUI
        self.title(title)
        self.geometry(f"{size[0]}x{size[1]}")
        self.minsize(size[0], size[1])
        
        # Create frames
        self.top_frame = tk.Frame(self, highlightbackground="black", highlightthickness=1)
        self.bottom_frame = tk.Frame(self, highlightbackground="black", highlightthickness=1)
        
        self.top_frame.grid(row=1, columnspan=4, padx=10, pady=8)
        self.bottom_frame.grid(row=4, columnspan=4, padx=10, pady=8)
        
        # Initialize menu
        self.menu = N4SortMenu(self, self.top_frame, self.bottom_frame)
        
        # Initialize progress tracker
        self.progress = ProgressTracker(self.bottom_frame)
        
        self.mainloop()
    
    def setup_logging(self):
        """Setup logging configuration with all logs under 'logs' directory"""
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create log file names with timestamps
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        main_log = log_dir / f"neoden4_processor_{timestamp}.log"
        pcr_log = log_dir / f"pcr_processing_{timestamp}.log"
        debug_log = log_dir / f"debug_{timestamp}.log"
        
        # Create formatters
        standard_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Main processing log - INFO and above
        main_handler = logging.FileHandler(main_log)
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(standard_formatter)
        root_logger.addHandler(main_handler)
        
        # PCR processing specific log - INFO and above
        pcr_handler = logging.FileHandler(pcr_log)
        pcr_handler.setLevel(logging.INFO)
        pcr_handler.setFormatter(standard_formatter)
        logging.getLogger('PCR_File_Splitter').addHandler(pcr_handler)
        
        # Debug log - DEBUG and above
        debug_handler = logging.FileHandler(debug_log)
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(debug_handler)
        
        # Console handler - INFO and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(standard_formatter)
        root_logger.addHandler(console_handler)
        
        # Log the initialization
        logging.info(f"Logging initialized - logs directory: {log_dir.absolute()}")
        logging.info(f"Main log: {main_log.name}")
        logging.info(f"PCR log: {pcr_log.name}")
        logging.info(f"Debug log: {debug_log.name}")

# ---- Improved Menu Class ----
class N4SortMenu(ttk.Frame):
    def __init__(self, parent, frame1, frame2):
        super().__init__(parent)
        self.parent = parent
        self.frame1 = frame1
        self.frame2 = frame2
        
        # Initialize data processor
        self.data_processor = PCBDataProcessor()
        
        # Create variables for sorting options
        self.sorting_vars = {
            'order': tk.StringVar(frame2, "True"),
            'option': tk.StringVar(frame2, "REFDES"),
            'inplace': tk.StringVar(frame2, "True"),
            'side': tk.StringVar(frame2, "False")
        }
    
        self.create_widgets(frame1, frame2)

    def open_pcbfile(self, t1: tk.Text, t2: tk.Text):
        """
        Open PCB file and automatically find matching template
        
        Args:
            t1: Text widget for PCB file path
            t2: Text widget for template file path
        """
        try:
            file = filedialog.askopenfilename(
                initialdir=self.parent.config.default_path,
                filetypes=[("CSV Files", "*.csv")]
            )
            
            if file:
                # Update PCB file entry
                t1.delete("1.0", tk.END)
                t1.insert(tk.END, file)
                
                # Get file path components
                self.filepath = os.path.split(file)[0]
                pcr_filename = Path(file).stem

                # Construct template filename and path
                template_filepath = os.path.join(self.filepath, f'Neoden4_Template{pcr_filename}.csv')
                template_exists = os.path.exists(template_filepath)

                # Update template file entry
                t2.delete("1.0", tk.END)
                if template_exists:
                    t2.configure(font=("Times New Roman", 12), foreground="white")
                    t2.insert(tk.END, template_filepath)
                else:
                    t2.insert(tk.END, "Neoden4_Template.csv NOT FOUND!!")
                    t2.configure(font=("Times New Roman", 12), foreground="RED")
                    # Optionally open file dialog for template selection
                    template_filepath = filedialog.askopenfilename(
                        initialdir=self.filepath,
                        filetypes=[("CSV Files", "*.csv")],
                        title="Select Template File"
                    )
                    if template_filepath:
                        t2.delete("1.0", tk.END)
                        t2.insert(tk.END, template_filepath)
                        t2.configure(font=("Times New Roman", 12), foreground="black")
                        
        except Exception as e:
            logging.error(f"Error opening PCB file: {str(e)}")
            self.show_error("File Error", f"Error opening PCB file: {str(e)}")

    def open_templatefile(self, t2: tk.Text):
        """
        Open template file manually
        
        Args:
            t2: Text widget for template file path
        """
        try:
            template_filename = filedialog.askopenfilename(
                initialdir=self.filepath if hasattr(self, 'filepath') else self.parent.config.default_path,
                filetypes=[("CSV Files", "*.csv")],
                title="Select Template File"
            )
            
            if template_filename:
                t2.delete("1.0", tk.END)
                t2.insert(tk.END, template_filename)
                t2.configure(font=("Times New Roman", 12), foreground="black")
                
        except Exception as e:
            logging.error(f"Error opening template file: {str(e)}")
            self.show_error("File Error", f"Error opening template file: {str(e)}")

    def create_widgets(self, frame1, frame2):
        """Create and arrange all widgets"""
        # Text entries
        self.pcb_file_entry = tk.Text(frame1, height=1.5, width=60)
        self.template_file_entry = tk.Text(frame1, height=1.5, width=60)
        self.pcb_width = ttk.Spinbox(frame1, name="pcb width", justify="left", 
                                    width=20, from_=0, to=5000)  # Increased upper limit
        
        # Configure widgets
        self.pcb_file_entry.configure(font=("Times New Roman", 12))
        self.template_file_entry.configure(font=("Times New Roman", 12))
        self.pcb_width.configure(font=("Times New Roman", 14), 
                            justify="left", increment=0.001)
        self.pcb_width.set("")  # Start empty to trigger auto-calculation
        
        # Grid layout
        self.pcb_file_entry.grid(row=1, columnspan=4, column=1, padx=6, pady=5)
        self.template_file_entry.grid(row=2, columnspan=4, column=1, padx=6, pady=5)
        self.pcb_width.grid(row=3, columnspan=2, column=1, padx=6, pady=5)

        # Create an info label for PCB width
        self.width_info = ttk.Label(frame1, 
                                text="(Leave empty for auto-calculation)", 
                                font=("Times New Roman", 10, "italic"))
        self.width_info.grid(row=3, column=3, padx=6, pady=5)
        
        # Create top row buttons
        buttons = [
            ("Open PCB-file", 1, 0, lambda: self.open_pcbfile(self.pcb_file_entry, self.template_file_entry), None),
            ("Open Template", 2, 0, lambda: self.open_templatefile(self.template_file_entry), None),
            ("PCB Width(mm)", 3, 0, None, None)  # Label only
        ]
        
        for text, row, col, command, _ in buttons:
            if command:  # Button
                btn = tk.Button(frame1, text=text, command=command)
            else:  # Label
                btn = ttk.Label(frame1, text=text)
            btn.grid(row=row, column=col, padx=6, pady=5)

        # Create button frame for centered buttons
        button_frame = ttk.Frame(frame2)
        button_frame.grid(row=6, column=0, columnspan=4, pady=10)

        # Configure grid weights for even spacing
        button_frame.grid_columnconfigure(0, weight=1)  # Space before first button
        button_frame.grid_columnconfigure(2, weight=1)  # Space between first and second buttons
        button_frame.grid_columnconfigure(4, weight=1)  # Space between second and third buttons
        button_frame.grid_columnconfigure(6, weight=1)  # Space after third button

        # Create centered action buttons
        split_btn = tk.Button(button_frame, text=" Split PCR ", command=self.process_pcb,
                            fg='green', font=("Times New Roman", 12, "bold"))
        gen_btn = tk.Button(button_frame, text="Generate CSV", command=self.generate_csv,
                        fg='red', font=("Times New Roman", 12, "bold"))
        help_btn = tk.Button(button_frame, text=" Help Guide ", command=self.show_help,
                            fg='blue', font=("Times New Roman", 12, "bold"))

        # Place buttons with even spacing
        split_btn.grid(row=0, column=1, padx=20)
        gen_btn.grid(row=0, column=3, padx=20)
        help_btn.grid(row=0, column=5, padx=20)

        # Create radio buttons
        self.create_radio_buttons()

    def create_radio_buttons(self):
        """Create sorting options with order selection"""
        # Create main configuration frame and center it
        config_frame = ttk.Frame(self.frame2)
        config_frame.grid(row=1, column=0, columnspan=4, pady=4)
        
        # Define header
        tk.Label(config_frame, text="Sorting Configuration", 
                font=("Times New Roman", 12, BOLD)).pack(pady=4)

        # Create container frame for both sort frames
        sort_container = ttk.Frame(self.frame2)
        sort_container.grid(row=2, column=0, columnspan=4, pady=5)
        
        # Configure container weights for centering
        sort_container.grid_columnconfigure(0, weight=1)  # Left margin
        sort_container.grid_columnconfigure(3, weight=1)  # Right margin

        # Create frame for sorting options
        sort_frame = ttk.LabelFrame(sort_container, text="Available Sort Options")
        sort_frame.grid(row=0, column=1, padx=10, pady=5)

        # Create frame for selected options
        selected_frame = ttk.LabelFrame(sort_container, text="Selected Sort Order")
        selected_frame.grid(row=0, column=2, padx=10, pady=5)

        # Available sorting options
        self.sort_options = {
            "REFDES": "Sort by RefDes",
            "XY_DIST": "Sort by xy-Location",
            "COMP_VALUE": "Sort by Comp Value",
            "SYM_NAME": "Sort by Comp Package"
        }

        # Create Listbox for available options
        self.available_listbox = tk.Listbox(sort_frame, height=6, width=25)
        for key, value in self.sort_options.items():
            self.available_listbox.insert(tk.END, value)
        self.available_listbox.pack(padx=5, pady=5)

        # Create Listbox for selected options
        self.selected_listbox = tk.Listbox(selected_frame, height=6, width=25)
        self.selected_listbox.pack(padx=5, pady=5)

        # Create control buttons frame and center it
        ctrl_frame = ttk.Frame(self.frame2)
        ctrl_frame.grid(row=3, column=0, columnspan=4, pady=5)

        # Configure control frame for centering
        ctrl_frame.grid_columnconfigure(0, weight=1)  # Left margin
        ctrl_frame.grid_columnconfigure(5, weight=1)  # Right margin

        # Add control buttons
        buttons = [
            ("→", self.add_sort_option),
            ("←", self.remove_sort_option),
            ("↑", lambda: self.move_option(-1)),
            ("↓", lambda: self.move_option(1))
        ]

        # Place control buttons in center
        for i, (text, command) in enumerate(buttons):
            ttk.Button(ctrl_frame, text=text, command=command, width=3).grid(
                row=0, column=i+1, padx=5)

        # Create frame for additional options and center it
        options_frame = ttk.LabelFrame(self.frame2, text="Sort Options")
        options_frame.grid(row=4, column=0, rowspan=2, columnspan=4, padx=10, pady=5)

        # Create inner frame for radio buttons and checkboxes
        inner_frame = ttk.Frame(options_frame)
        inner_frame.pack(expand=True, fill='x', padx=5, pady=5)

        # Configure columns for even spacing
        for i in range(5):
            inner_frame.grid_columnconfigure(i, weight=1)

        # Add sort order option
        self.sort_order_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(inner_frame, text="Ascending", variable=self.sort_order_var,
                        value=True).grid(row=0, column=0)
        ttk.Radiobutton(inner_frame, text="Descending", variable=self.sort_order_var,
                        value=False).grid(row=0, column=1)

        # Add sort inplace option
        self.sort_inplace_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(inner_frame, text="Sort Inplace",
                        variable=self.sort_inplace_var).grid(row=0, column=2)

        # Add PCB side selection
        self.pcb_side_var = tk.StringVar(value="False")
        ttk.Radiobutton(inner_frame, text="Top", variable=self.pcb_side_var,
                        value="False").grid(row=0, column=3)
        ttk.Radiobutton(inner_frame, text="Bottom", variable=self.pcb_side_var,
                        value="True").grid(row=0, column=4)

        # Add padding to all grid cells in inner frame
        for child in inner_frame.winfo_children():
            child.grid_configure(padx=10, pady=2)

    def create_file_input(self, label: str, row: int, command: callable) -> tk.Text:
        tk.Label(self.frame1, text=label).grid(row=row, column=0, padx=6, pady=5)
        entry = tk.Text(self.frame1, height=1.5, width=60)
        entry.grid(row=row, column=1, columnspan=3, padx=6, pady=5)
        
        tk.Button(
            self.frame1,
            text=f"Open {label}",
            command=command
        ).grid(row=row, column=4, padx=6, pady=5)
        
        return entry
    
    def open_file(self, entry_widget: tk.Text):
        try:
            filepath = filedialog.askopenfilename(
                initialdir=self.parent.config.default_path,
                filetypes=[("CSV Files", "*.csv")]
            )
            if filepath:
                entry_widget.delete("1.0", tk.END)
                entry_widget.insert(tk.END, filepath)
                
                # If this is PCB file, try to find matching template
                if entry_widget == self.pcb_file_entry:
                    self.find_matching_template()
        except Exception as e:
            logging.error(f"Error opening file: {str(e)}")
            self.show_error("Error opening file", str(e))
    
    def process_files(self):
        try:
            pcb_file = self.pcb_file_entry.get("1.0", tk.END).strip()
            template_file = self.template_file_entry.get("1.0", tk.END).strip()
            pcb_width = float(self.pcb_width.get())
            
            # Validate inputs
            if not all([pcb_file, template_file, pcb_width > 0]):
                raise PCBProcessingError("Missing or invalid inputs")
            
            # Process files with progress updates
            def update_progress(current, total, status):
                self.parent.progress.update_progress(current, total, status)
            
            self.data_processor.process_files(
                pcb_file,
                template_file,
                pcb_width,
                self.sorting_vars,
                update_progress
            )
            
            self.show_success("Processing complete!")
            logging.info("Processing complete!")
            
        except Exception as e:
            logging.error(f"Error processing files: {str(e)}")
            self.show_error("Processing Error", str(e))
           
    def get_sort_configuration(self) -> Dict:
        """Get current sorting configuration"""
        selected_options = self.selected_listbox.get(0, tk.END)
        
        # Convert display names back to column names
        reverse_lookup = {v: k for k, v in self.sort_options.items()}
        sort_columns = [reverse_lookup[option] for option in selected_options]
        
        return {
            'columns': sort_columns,
            'ascending': self.sort_order_var.get(),
            'inplace': self.sort_inplace_var.get(),
            'side': str(self.pcb_side_var.get())  # Convert to string
        }

    def generate_csv(self):
            """Handle CSV generation process"""
            try:
                # Get input values
                pcb_file = self.pcb_file_entry.get("1.0", tk.END).strip()
                template_file = self.template_file_entry.get("1.0", tk.END).strip()
                pcb_width = float(self.pcb_width.get() or 0)  # Convert empty string to 0

                # Validate inputs
                if not all([pcb_file, template_file]):
                    raise ValueError("Please select both PCB and template files")

                # Get sorting configuration
                sort_config = self.get_sort_configuration()
                
                if not sort_config['columns']:
                    if not messagebox.askyesno(
                        "No Sort Options",
                        "No sorting options selected. Continue anyway?"
                    ):
                        return

                # Create callback for width updates
                def update_width(width: float):
                    self.pcb_width.delete(0, tk.END)
                    self.pcb_width.insert(0, f"{width:.3f}")
                    self.frame1.update_idletasks()

                # Generate CSV with width callback
                output_file = self.data_processor.generate_csv(
                    pcb_file,
                    template_file,
                    pcb_width,
                    sort_config,
                    lambda current, total, status: self.parent.progress.update_progress(
                        current, total, status),
                    update_width  # Add width callback
                )

                messagebox.showinfo(
                    "Success",
                    f"CSV file generated successfully:\n{output_file}"
                )

            except Exception as e:
                messagebox.showerror(
                    "Error",
                    f"Error generating CSV:\n{str(e)}"
                )
                logging.error(f"CSV generation error: {str(e)}", exc_info=True)

    def show_error(self, title: str, message: str):
        """Display error message to user"""
        tk.messagebox.showerror(title, message)

    def show_success(self, message: str):
        """Display success message to user"""
        tk.messagebox.showinfo("Success", message)

    def find_matching_template(self):
        """Try to find matching template file for selected PCB file"""
        try:
            pcb_file = self.pcb_file_entry.get("1.0", tk.END).strip()
            if pcb_file:
                pcb_path = Path(pcb_file)
                template_path = pcb_path.parent / f"Neoden4_Template_{pcb_path.stem}.csv"
                
                if template_path.exists():
                    self.template_file_entry.delete("1.0", tk.END)
                    self.template_file_entry.insert(tk.END, str(template_path))
                    self.template_file_entry.configure(foreground="black")
                else:
                    self.template_file_entry.delete("1.0", tk.END)
                    self.template_file_entry.insert(tk.END, "Template file not found!")
                    self.template_file_entry.configure(foreground="red")
        except Exception as e:
            logging.error(f"Error finding template: {str(e)}")

    def add_sort_option(self):
        """Add selected option to sort order"""
        selection = self.available_listbox.curselection()
        if selection:
            index = selection[0]
            value = self.available_listbox.get(index)
            if value not in self.selected_listbox.get(0, tk.END):
                self.selected_listbox.insert(tk.END, value)

    def remove_sort_option(self):
        """Remove selected option from sort order"""
        selection = self.selected_listbox.curselection()
        if selection:
            self.selected_listbox.delete(selection[0])

    def move_option(self, direction):
        """Move selected option up or down in the sort order"""
        selection = self.selected_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        value = self.selected_listbox.get(index)
        
        new_index = index + direction
        if 0 <= new_index < self.selected_listbox.size():
            self.selected_listbox.delete(index)
            self.selected_listbox.insert(new_index, value)
            self.selected_listbox.selection_set(new_index)

    def process_pcb(self):
        """Handle PCR file Splitting"""
        try:
            # Get PCR file
            pcr_file = filedialog.askopenfilename(
                title="Select PCR file",
                filetypes=[("CSV Files", "*.csv")]
            )
            
            if not pcr_file:
                return
                
            # Get directory and verify required files
            file_dir = os.path.dirname("/Users/godwinm.mayers/Neoden4Assembly/pcr_files/")
            required_files = {
                "Component Table": "Component_Table.csv",
                "Neoden4 Template": "Neoden4.csv",
                "Configuration": "configuration.json",
                "Neoden4_Nozzles": "Neoden4_Nozzles.csv"
            }
            
            # Check for missing files
            missing_files = []
            file_paths = {}
            for name, filename in required_files.items():
                path = os.path.join(file_dir, filename)
                if not os.path.exists(path):
                    missing_files.append(name)
                else:
                    file_paths[name] = path
            
            if missing_files:
                tk.messagebox.showerror(
                    "Missing Files",
                    f"Missing required files in {file_dir}:\n" +
                    "\n".join(missing_files)
                )
                return
            
            # Process PCR file with progress tracking
            pcrSplitter = PCR_File_Splitter(
                pcr_file,
                file_paths["Component Table"],
                file_paths["Neoden4 Template"],
                file_paths["Configuration"],
                progress_callback=lambda current, total, status: self.parent.progress.update_progress(
                    current, total, status)
            )
            
            # Clear old progress
            self.parent.progress.update_progress(0, 100, "Starting PCR processing...")
            
            # Process files
            pcrSplitter.process_files()
            
            tk.messagebox.showinfo(
                "Success",
                "PCR file processed successfully!\nTemplate files have been created."
            )
                
        except Exception as e:
            tk.messagebox.showerror(
                "Error",
                f"Error processing PCR file:\n{str(e)}"
            )
            logging.error(f"PCR processing error: {str(e)}", exc_info=True)

    def sort_generated_files(self):
        """Apply custom sorting to previously generated files"""
        try:
            # Get generated files (e.g., N4_*_Topa.csv, N4_*_Bota.csv)
            file_to_sort = filedialog.askopenfilename(
                title="Select generated N4 file to sort",
                filetypes=[("CSV Files", "N4_*_*.csv")]
            )
            
            if not file_to_sort:
                return

            # Get sorting configuration
            sort_config = self.get_sort_configuration()
            
            # Verify sorting options selected
            if not sort_config['columns']:
                if not messagebox.askyesno(
                    "No Sort Options",
                    "No sorting options selected. Continue anyway?"
                ):
                    return

            # Read and sort file
            df = pd.read_csv(file_to_sort)
            
            # Split template and component data
            template_data = df[df['#Feeder'].isin(['stack', 'mark', 'markext', 'test', 
                                                'mirror_create', 'mirror', '#SMD'])]
            component_data = df[df['#Feeder'] == 'comp']

            # Apply sorting to component data
            if sort_config['columns']:
                ascending = [sort_config['ascending']] * len(sort_config['columns'])
                component_data = component_data.sort_values(
                    by=sort_config['columns'],
                    ascending=ascending,
                    inplace=False
                )

            # Recombine data
            sorted_df = pd.concat([template_data, component_data])
            
            # Save sorted file
            output_path = file_to_sort.replace('.csv', '_sorted.csv')
            sorted_df.to_csv(output_path, index=False)
            
            messagebox.showinfo(
                "Success",
                f"File sorted successfully!\nSaved as: {os.path.basename(output_path)}"
            )

        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Error sorting file:\n{str(e)}"
            )
            logging.error(f"Sorting error: {str(e)}", exc_info=True)

    def show_help(self):
        """Display help documentation in a new window"""
        help_window = tk.Toplevel(self)
        help_window.title("Neoden4 CSV Creator - User Guide")
        help_window.geometry("900x700")

        # Create main frame with padding
        main_frame = ttk.Frame(help_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabbed sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create tabs
        overview_tab = ttk.Frame(notebook)
        workflow_tab = ttk.Frame(notebook)
        troubleshoot_tab = ttk.Frame(notebook)
        
        notebook.add(overview_tab, text='Overview')
        notebook.add(workflow_tab, text='Workflow')
        notebook.add(troubleshoot_tab, text='Troubleshooting')

        # Helper function to create scrolled text widget
        def create_text_widget(parent):
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.BOTH, expand=True)
            
            text = tk.Text(
                frame,
                wrap=tk.WORD,
                font=("Arial", 14),
                padx=10,
                pady=10
            )
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            return text

        # Create text widgets for each tab
        overview_text = create_text_widget(overview_tab)
        workflow_text = create_text_widget(workflow_tab)
        troubleshoot_text = create_text_widget(troubleshoot_tab)

        # Content for Overview tab
        overview_content = """# Neoden4 File Creator

    ## Overview
    The Neoden4 File Creator is a tool for preparing PCB assembly files for use with Neoden4 pick-and-place machines.
    It processes PCR (Place Component Report) files into the necessary formats for both top and bottom assembly.

    ## Key Features
    - Automatic file splitting for top and bottom assembly
    - Component sorting with multiple options
    - Template file management
    - Fiducial handling
    - Manual placement identification

    ## Prerequisites
    - Python 3.x installed
    - Required Python packages: pandas, numpy, tkinter
    - PCR file exported from Allegro in CSV format
    - Access to Neoden4Assembly directory structure

    ## Directory Structure
    /Neoden4Assembly/
    ├── PCB_Assembly/
    │   └── BoardName/
    │       └── BOARD_NAME.csv
    ├── pcr_files/
    │   ├── Component_Table.csv
    │   ├── Neoden4.csv
    │   └── configuration.json
    └── N4_CSV_Creator_v2b.py"""

        # Content for Workflow tab
        workflow_content = """# Working with Neoden4 File Creator

    ## Step 1: PCR File Preparation
    1. Export Allegro PCR file as CSV
    2. Create directory: /Neoden4Assembly/PCB_Assembly/BoardName/
    3. Save CSV file in new directory
    4. Rename fiducials to FID1, FID2, etc.

    ## Step 2: File Processing
    1. Launch application: python3 N4_CSV_Creator_v2a.py
    2. Click "Split PCR"
    3. Select your PCR file
    4. The tool will generate the following:
    •  BoardName_(Topa/b, Bota/b)
    •  Neoden4_TemplateBoardName(Topa/b, Bota/b)
    •  Manual_Placement_(Top, Bot)

    ## Step 3: Machine Calibration
    1. Place PCB on Neoden4 machine
    2. Upload template via USB
    3. Calibrate using fiducials
    4. Save and export modified template
    5. Replace original template in board directory

    ## Step 4: Generate Placement Files
    1. Click 'Open PCB-file' and select matching board file
    2. For bottom assembly: Enter board width
    3. Select sorting options:
    • Reference Designator
    • XY Location
    • Component Value
    • Component Package
    4. Click "Generate CSV"
    5. The tool will generate the following:
    • N4_BoardName_(Topx/Botx)

    ## Step 5: Component Management
    - Review Manual_Placement files
    - Update Component Table as needed
    - Verify component assignments"""

        # Content for Troubleshooting tab
        troubleshoot_content = """# Troubleshooting Guide

    ## Common Issues

    ### Value Variations
    Components that may need standardization:

    Resistors:
    ✓ Correct: 10K
    ✗ Fix: 10k, 10 kOhm, 10 KOhm

    Other Components:
    ✓ Correct: 100 Ohm
    ✗ Fix: 100, 100 OHM, 100Ω

    ### File Issues
    - Missing template files
    - Incorrect fiducial naming
    - Board width errors
    - Component table mismatches

    ## Validation Steps
    1. Check fiducial names (FID1, FID2)
    2. Verify board width for bottom assembly
    3. Confirm Component Table entries
    4. Review template file matches

    ## Component Table Format
    Required format:
    Reel    Footprint	      Value	             Pick height	    Pick delay	    Place Height	    Place Delay  .....
    8	CAP0603	    Footprint/Value	    2.8	            100	                        3                   100	     ......... 
    8	CAP0402	    Footprint/Value	    2.1	            100                         2.7                 100	     .........
    8	RES0603	    Footprint/Value	    2.2	            100                         2.6                 100	     .........	
    8	SOD-123	    Footprint/Value	    2.1	            100	                        3.1                 100	     .........	

    ## Best Practices
    1. Use consistent value formatting
    2. Update Component Table regularly
    3. Verify fiducial detection
    4. Back up templates
    5. Double-check measurements

    ## Support Files
    Required files in pcr_files directory:
    - Component_Table.csv
    - Neoden4.csv
    - configuration.json"""

        # Insert content and apply formatting
        for text_widget, content in [
            (overview_text, overview_content),
            (workflow_text, workflow_content),
            (troubleshoot_text, troubleshoot_content)
        ]:
            text_widget.insert("1.0", content)
            
            # Apply formatting
            for line in content.split('\n'):
                if line.startswith('# '):
                    start = text_widget.search(line, "1.0", tk.END)
                    end = f"{start}+{len(line)}c"
                    text_widget.tag_add("heading1", start, end)
                elif line.startswith('## '):
                    start = text_widget.search(line, "1.0", tk.END)
                    end = f"{start}+{len(line)}c"
                    text_widget.tag_add("heading2", start, end)
                elif line.startswith('• '):
                    start = text_widget.search(line, "1.0", tk.END)
                    end = f"{start}+{len(line)}c"
                    text_widget.tag_add("bullet", start, end)
                elif '✓' in line:
                    start = text_widget.search(line, "1.0", tk.END)
                    end = f"{start}+{len(line)}c"
                    text_widget.tag_add("correct", start, end)
                elif '✗' in line:
                    start = text_widget.search(line, "1.0", tk.END)
                    end = f"{start}+{len(line)}c"
                    text_widget.tag_add("incorrect", start, end)

            # Configure tags
            text_widget.tag_configure("heading1", font=("Arial", 16, "bold"))
            text_widget.tag_configure("heading2", font=("Arial", 14, "bold"))
            text_widget.tag_configure("bullet", font=("Arial", 11))
            text_widget.tag_configure("correct", foreground="green")
            text_widget.tag_configure("incorrect", foreground="red")
            
            # Make text read-only
            text_widget.config(state='disabled')

        # Add close button
        close_btn = ttk.Button(
            help_window,
            text="Close",
            command=help_window.destroy
        )
        close_btn.pack(pady=5)

# ---- Data Processing Class ----
class PCBDataProcessor:
    def __init__(self):
        """Initialize the PCB data processor"""
        self.logger = logging.getLogger('PCBDataProcessor')
        self.logger.info("PCBDataProcessor initialized")
        self.nozzle_rotations = self._initialize_nozzle_rotations()
        
    def _initialize_nozzle_rotations(self) -> Dict[str, List[float]]:
        """Initialize nozzle rotation capabilities"""
        try:
            # Read the nozzle configuration file
            filepath = os.path.dirname("/Users/godwinm.mayers/Neoden4Assembly/pcr_files/")
            nozzle_file = os.path.join(filepath, "Neoden4_Nozzles.csv")

            if not os.path.exists(nozzle_file):
                tk.messagebox.showerror(
                    "Missing Files",
                    f"Missing required files in {nozzle_file}:\n" 
                )
                return
            
            nozzle_config_df = pd.read_csv(nozzle_file)
            nozzle_rotations = {}
            for _, row in nozzle_config_df.iterrows():
                # Convert string of rotations to list of floats
                rotations = [float(angle.strip()) for angle in row['Rotation'].split(',')]
                nozzle_rotations[str(row['Nozzle'])] = rotations
            
            self.logger.info(f"Loaded nozzle rotations: {nozzle_rotations}")
            return nozzle_rotations
        except Exception as e:
            self.logger.error(f"Error loading nozzle rotations: {str(e)}")
            raise PCBProcessingError(f"Failed to load nozzle configuration: {str(e)}")

    def _normalize_angle(self, angle: float) -> float:
        """Normalize angle to range [-180, 180]"""
        angle = angle % 360
        if angle > 180:
            angle -= 360
        return angle

    def _get_compatible_nozzles(self, component_rotation: float) -> List[str]:
        """Get list of nozzles compatible with the required rotation"""
        normalized_rotation = self._normalize_angle(component_rotation)
        compatible_nozzles = []
        
        for nozzle, allowed_rotations in self.nozzle_rotations.items():
            if any(abs(normalized_rotation - self._normalize_angle(allowed)) < 0.1 
                  for allowed in allowed_rotations):
                compatible_nozzles.append(nozzle)
                
        self.logger.debug(f"Compatible nozzles for rotation {component_rotation}: {compatible_nozzles}")
        return compatible_nozzles

    def create_component_key(self,pcr_row: pd.Series) -> str:
        """
        Create a consistent component key for matching between PCR and template
        
        Args:
            pcr_row: Row from PCR file containing component info
            
        Returns:
            String key in format "FOOTPRINT/VALUE"
            
        Example:
            Input PCR row:
            - SYM_NAME: CAP0603
            - COMP_VALUE: 0.1UF
            Returns: "CAP0603/0.1UF"
        """
        try:
            footprint = str(pcr_row['SYM_NAME']).strip()
            value = str(pcr_row['COMP_VALUE']).strip()
            
            # Create combined key
            key = f"{footprint}/{value}"
            return key
            
        except Exception as e:
            logging.error(f"Error creating component key: {str(e)}")
            return ""

    def nozzle_feeder_assignment(self, pcr_path: str, pcb_df: pd.DataFrame, n4_df: pd.DataFrame) -> pd.DataFrame:
        """
        Assign nozzles and feeders to components based on rotation capabilities
        """
        try:
            self.logger.info("Starting nozzle and feeder assignment with rotation checking")
            
            # Create mapping of value to feeder information
            n4_map = {}
            for _, row in n4_df.iterrows():
                if row['#Feeder'] != 'stack':
                    continue
                    
                value = str(row['Value']).strip()
                key = value
                feeder_id = str(row['Feeder ID'])
                
                # Get list of available nozzles for this feeder
                # Handle single and multi-digit nozzle numbers
                nozzle_str = str(row['Nozzle'])
                if len(nozzle_str) == 1:
                    available_nozzles = [nozzle_str]
                else:
                    available_nozzles = [n for n in nozzle_str]
                
                if key not in n4_map:
                    n4_map[key] = {
                        '#Feeder': feeder_id,
                        'Available_Nozzles': available_nozzles
                    }
                print("nozzle_str",nozzle_str)
            # Track feeder and nozzle usage
            feeder_nozzle_assignment = defaultdict(list)
            feeder_component_counts = defaultdict(int)
            unmatched_rows = []

            # First pass: Count components per feeder for FEEDER_20_MAX_COUNT check
            for _, row in pcb_df.iterrows():
                comp_value = str(row['COMP_VALUE']).strip()
                sym_name = str(row['SYM_NAME']).strip()
                combined_value = f"{sym_name}/{comp_value}"
                
                if combined_value in n4_map:
                    feeder_id = n4_map[combined_value]['#Feeder']
                    feeder_component_counts[feeder_id] += 1

            # Process each component
            for index, row in pcb_df.iterrows():
                comp_value = str(row['COMP_VALUE']).strip()
                sym_name = str(row['SYM_NAME']).strip()
                combined_value = f"{sym_name}/{comp_value}"
                rotation = float(row['SYM_ROTATE'])
                
                self.logger.debug(f"Processing component: {row['REFDES']}, "
                                f"Value: {combined_value}, Rotation: {rotation}")
                
                if combined_value in n4_map:
                    feeder_id = n4_map[combined_value]['#Feeder']
                    
                    # Check component count limit for feeder 20
                    if feeder_id == '20' and feeder_component_counts[feeder_id] > FEEDER_20_MAX_COUNT:
                        self.logger.warning(
                            f"Feeder 20 component count ({feeder_component_counts[feeder_id]}) "
                            f"exceeds maximum ({FEEDER_20_MAX_COUNT})"
                        )
                        unmatched_rows.append(row)
                        continue
                    
                    # Get available nozzles for this feeder
                    available_nozzles = n4_map[combined_value]['Available_Nozzles']
                    
                    # Get compatible nozzles for the required rotation
                    compatible_nozzles = self._get_compatible_nozzles(rotation)
                    
                    # Find intersection of available and compatible nozzles
                    valid_nozzles = [n for n in available_nozzles if n in compatible_nozzles]
                    
                    self.logger.debug(f"Component {row['REFDES']}: "
                                    f"Available nozzles: {available_nozzles}, "
                                    f"Compatible nozzles: {compatible_nozzles}, "
                                    f"Valid nozzles: {valid_nozzles}")
                    
                    if valid_nozzles:
                        # Choose the least used compatible nozzle
                        nozzle_counts = {n: feeder_nozzle_assignment[feeder_id].count(n) 
                                       for n in valid_nozzles}
                        chosen_nozzle = min(nozzle_counts.keys(), 
                                          key=lambda k: nozzle_counts[k])
                        
                        # Assign feeder and nozzle
                        pcb_df.at[index, '#Feeder'] = 'comp'
                        pcb_df.at[index, 'Feeder ID'] = feeder_id
                        pcb_df.at[index, 'Nozzle'] = chosen_nozzle
                        
                        # Track assignment
                        feeder_nozzle_assignment[feeder_id].append(chosen_nozzle)
                        
                        self.logger.info(
                            f"Assigned {row['REFDES']} (rotation: {rotation}) to "
                            f"feeder {feeder_id}, nozzle {chosen_nozzle}"
                        )
                    else:
                        self.logger.warning(
                            f"No compatible nozzle found for {row['REFDES']} "
                            f"rotation {rotation}"
                        )
                        unmatched_rows.append(row)
                else:
                    self.logger.warning(f"No match found for component: {row['REFDES']}")
                    unmatched_rows.append(row)

            # Handle unmatched components
            if unmatched_rows:
                unmatched_df = pd.DataFrame(unmatched_rows)
                unmatched_file = os.path.join(pcr_path, 'manual_assignment.csv')
                unmatched_df.to_csv(unmatched_file, index=False)
                self.logger.warning(f"Written {len(unmatched_rows)} unmatched components to {unmatched_file}")

            # Log assignment statistics
            for feeder_id, assignments in feeder_nozzle_assignment.items():
                nozzle_counts = Counter(assignments)
                self.logger.info(f"Feeder {feeder_id} nozzle usage: {dict(nozzle_counts)}")
                if feeder_id == '20':
                    self.logger.info(f"Feeder 20 total component count: {feeder_component_counts['20']}")

            return pcb_df

        except Exception as e:
            self.logger.error(f"Error in nozzle_feeder_assignment: {str(e)}")
            raise PCBProcessingError(f"Failed to assign nozzles and feeders: {str(e)}")

    def process_board_side(self, pcb_df: pd.DataFrame, pcb_width: float,
                          sort_config: Dict) -> pd.DataFrame:
        """Process board side and apply mirroring if needed"""
        try:
            # Get mirror option directly from config
            mirror_option = sort_config['side']  # Now a string, not StringVar
            
            if mirror_option == "True":  # Bottom side
                if float(pcb_width) <= 0:
                    raise PCBProcessingError("PCB width required for bottom side processing")
                    
                # Filter and process bottom side components
                pcb_df = pcb_df[pcb_df['SYM_MIRROR'] == 'YES']
                pcb_df['SYM_X'] = pcb_df['SYM_X'].apply(lambda x: float(pcb_width) - float(x))
                pcb_df['SYM_ROTATE'] = pcb_df['SYM_ROTATE'].apply(lambda x: 180 - float(x))
            else:  # Top side
                pcb_df = pcb_df[pcb_df['SYM_MIRROR'] == 'NO']

            return pcb_df

        except Exception as e:
            logging.error(f"Error in process_board_side: {str(e)}")
            raise PCBProcessingError(f"Failed to process board side: {str(e)}")

    def get_pcb_width_from_fiducials(self, pcb_df: pd.DataFrame) -> float:
        """
        Calculate PCB width from fiducial positions, with specific handling for 2-fiducial cases.
        
        For 2 fiducials, the logic is:
        1. If fiducials are diagonally opposite (different X and Y):
        - Use the one with larger X value
        2. If fiducials are on same vertical line (same X):
        - Flag as warning, might need manual width
        3. If fiducials are on same horizontal line (same Y):
        - Use the larger X value
        
        Args:
            pcb_df: DataFrame containing PCB component data
            
        Returns:
            float: Calculated PCB width from fiducial position
            
        Example cases with 2 fiducials:
        Case 1 (Diagonal):         Case 2 (Horizontal):      Case 3 (Vertical):
        FID2 *                     FID1 *    * FID2          FID2 *
                                                                
                                                                
        FID1 *                                                FID1 *
        """
        try:
            # Filter for fiducials
            fiducials = pcb_df[pcb_df['REFDES'].str.contains('FID', case=False, na=False)]
            
            if fiducials.empty:
                self.logger.warning("No fiducials found in PCB data")
                return 0.0
                
            # Log found fiducials
            self.logger.info(f"Found {len(fiducials)} fiducials:")
            for _, fid in fiducials.iterrows():
                self.logger.info(f"  {fid['REFDES']}: X={fid['SYM_X']:.3f}, Y={fid['SYM_Y']:.3f}")

            # Special handling for 2 fiducials
            if len(fiducials) == 2:
                fid1 = fiducials.iloc[0]
                fid2 = fiducials.iloc[1]
                
                x1, y1 = float(fid1['SYM_X']), float(fid1['SYM_Y'])
                x2, y2 = float(fid2['SYM_X']), float(fid2['SYM_Y'])
                
                # Calculate differences
                x_diff = abs(x2 - x1)
                y_diff = abs(y2 - y1)
                
                self.logger.info(
                    f"Two fiducial analysis:\n"
                    f"  FID1: ({x1:.3f}, {y1:.3f})\n"
                    f"  FID2: ({x2:.3f}, {y2:.3f})\n"
                    f"  X difference: {x_diff:.3f}mm\n"
                    f"  Y difference: {y_diff:.3f}mm"
                )

                # Check fiducial arrangement
                if x_diff < 0.001:  # Same vertical line
                    self.logger.warning(
                        "Fiducials are on same vertical line. "
                        "Width calculation may not be accurate."
                    )
                    return max(x1, x2)
                    
                elif y_diff < 0.001:  # Same horizontal line
                    self.logger.info("Fiducials are on same horizontal line")
                    return max(x1, x2)
                    
                else:  # Diagonal arrangement
                    self.logger.info("Fiducials are diagonally arranged")
                    # For diagonal arrangement, use the larger X value
                    max_x = max(x1, x2)
                    if x1 > x2:
                        self.logger.info(f"Using FID1 position ({x1:.3f}, {y1:.3f}) for width")
                    else:
                        self.logger.info(f"Using FID2 position ({x2:.3f}, {y2:.3f}) for width")
                    return max_x

            # If more than 2 fiducials, use original logic
            else:
                # Sort by X descending and Y ascending
                sorted_fiducials = fiducials.sort_values(['SYM_X', 'SYM_Y'], ascending=[False, True])
                rightmost_fid = sorted_fiducials.iloc[0]
                pcb_width = float(rightmost_fid['SYM_X'])
                
                self.logger.info(
                    f"Using rightmost fiducial {rightmost_fid['REFDES']} "
                    f"at position ({pcb_width:.3f}, {float(rightmost_fid['SYM_Y']):.3f})"
                )
                return pcb_width

        except Exception as e:
            self.logger.error(f"Error calculating PCB width from fiducials: {str(e)}")
            return 0.0

    def verify_pcb_width(self, width: float, pcb_df: pd.DataFrame) -> None:
        """
        Verify calculated PCB width against component positions
        
        Args:
            width: Calculated PCB width
            pcb_df: DataFrame containing PCB component data
        
        Raises:
            PCBProcessingError if width appears invalid
        """
        try:
            # Get maximum X position of any component
            max_component_x = pcb_df['SYM_X'].max()
            
            # Add some margin (e.g., 5mm) to account for component size
            margin = 5.0
            
            if width < (max_component_x + margin):
                self.logger.warning(
                    f"Calculated width ({width:.3f}mm) is less than maximum component "
                    f"position ({max_component_x:.3f}mm + {margin}mm margin)"
                )
                raise PCBProcessingError(
                    f"Calculated PCB width {width:.3f}mm appears too small. "
                    "Please verify fiducial positions or provide width manually."
                )
                
        except Exception as e:
            self.logger.error(f"Error verifying PCB width: {str(e)}")
            raise

    def generate_csv(self, pcb_file: str, template_file: str, pcb_width: float,
                    sort_config: Dict, 
                    progress_callback: Optional[Callable[[int, int, str], None]] = None,
                    width_callback: Optional[Callable[[float], None]] = None) -> str:
        """Main method to process PCB data and generate Neoden4 CSV file"""
        try:
            # Read input files
            pcb_df = pd.read_csv(pcb_file.strip())
            n4_df = pd.read_csv(template_file.strip())
            
            if progress_callback:
                progress_callback(1, 5, "Files loaded successfully")

            # Validate dataframes
            if pcb_df.empty:
                raise PCBProcessingError("PCB file contains no data")
            if n4_df.empty:
                raise PCBProcessingError("Template file contains no data")

            # Log input data statistics
            self.logger.info(f"PCB file loaded: {len(pcb_df)} components")
            self.logger.info(f"Template file loaded: {len(n4_df)} entries")
            self.logger.info(f"Sort configuration: {sort_config}")

            # Handle PCB width
            if pcb_width <= 0:
                self.logger.info("No PCB width provided, calculating from fiducial positions...")
                pcb_width = self.get_pcb_width_from_fiducials(pcb_df)
                
                if pcb_width <= 0:
                    raise PCBProcessingError(
                        "Could not calculate PCB width from fiducials. "
                        "Please provide width manually."
                    )
                
                # Update GUI if callback provided
                if width_callback:
                    width_callback(pcb_width)
                    self.logger.info(f"Updated GUI with calculated PCB width: {pcb_width:.3f}mm")
            else:
                self.logger.info(f"Using provided PCB width: {pcb_width:.3f}mm")

            # Process board side
            pcb_df = self.process_board_side(pcb_df, pcb_width, sort_config)
            if progress_callback:
                progress_callback(3, 5, "Board side processed")
                
            # Verify required columns before processing
            required_cols = ['REFDES', 'COMP_VALUE', 'SYM_NAME', 'SYM_X', 'SYM_Y', 'SYM_ROTATE', 'SYM_MIRROR']
            missing_cols = [col for col in required_cols if col not in pcb_df.columns]
            if missing_cols:
                raise PCBProcessingError(f"Missing required columns in PCB data: {missing_cols}")

            # Log component processing start
            self.logger.info("Starting component processing...")
            self.logger.info(f"PCB components to process: {len(pcb_df)}")

            # Process components with proper arguments
            processed_df = self.process_components(
                pcb_df=pcb_df,  # PCB component data
                n4_df=n4_df,    # Template data
                sort_config=sort_config,  # Sorting configuration
                pcr_path=os.path.dirname(pcb_file)  # Directory for saving unmatched components
            )
            
            if progress_callback:
                progress_callback(4, 5, "Components processed")

            # Verify processed data
            if processed_df.empty:
                raise PCBProcessingError("No components were processed")
                
            self.logger.info(f"Component processing complete. Processed {len(processed_df)} components")

            # Generate output file
            output_file = self.generate_output(processed_df, n4_df, pcb_file)
            if progress_callback:
                progress_callback(5, 5, "CSV file generated")

            # Log success
            self.logger.info(f"Successfully generated output file: {output_file}")
            return output_file

        except Exception as e:
            self.logger.error(f"Error in generate_csv: {str(e)}")
            raise PCBProcessingError(f"Failed to generate CSV: {str(e)}")

    def process_components(self, pcb_df: pd.DataFrame, n4_df: pd.DataFrame,
                        sort_config: Dict, pcr_path: str) -> pd.DataFrame:
        """
        Process and sort components with coordinate transformation and rotation adjustment
        
        Args:
            pcb_df: PCB component data
            n4_df: Neoden4 template data
            sort_config: Sorting configuration
            pcr_path: Path to save unmatched components
            
        Returns:
            Processed DataFrame
        """
        try:
             # First get fiducial information before filtering them out
            fiducial_info = self.get_fiducial_info(n4_df, pcb_df)

              # Log processing statistics before nozzle_feeder_assignments
            self.logger.info(f"Processed {pcb_df} components")
            
            
            # Calculate distances if XY_DIST is in sort columns
            if 'XY_DIST' in sort_config.get('columns', []):
                pcb_df['XY_DIST'] = pcb_df.apply(
                    lambda row: math.dist(
                        [row['SYM_X'], row['SYM_Y']], 
                        [fiducial_info['offset_x'], fiducial_info['offset_y']]
                    ), 
                    axis=1
                )

            
            # Sort components using configured options
            if sort_config['columns']:
                ascending = [sort_config['ascending']] * len(sort_config['columns'])
                pcb_df.sort_values(
                    by=sort_config['columns'],
                    ascending=ascending,
                    inplace=sort_config['inplace']
                )
           

            # Clean up temporary columns
            #if 'XY_DIST' in pcb_df.columns and 'XY_DIST' not in sort_config['columns']:
            pcb_df.drop(columns=['XY_DIST'], inplace=True)
            pcb_df.drop(columns=['COMP_DEVICE_TYPE'], inplace=True)
            pcb_df.drop(columns=['COMP_TOL'], inplace=True)

            # Add Neoden4 required columns
            pcb_df.insert(0, "#Feeder", ['comp'] * len(pcb_df))
            pcb_df.insert(1, "Feeder ID", ['1'] * len(pcb_df))
            pcb_df.insert(2, "Nozzle", ['1'] * len(pcb_df))

            

            # Calculate and apply coordinate transformation
            transform = self.calculate_homography(
                fiducial_info['points_i'],
                fiducial_info['points_m']
            )
            pcb_df = self.apply_transform(pcb_df, transform)

           
            # Assign nozzles and feeders

            pcb_df = self.nozzle_feeder_assignment(pcr_path, pcb_df, n4_df)

             # Filter out fiducials from processing
            pcb_df = pcb_df[
                ~pcb_df['REFDES'].str.contains("FID", na=False, case=True)&
                ~pcb_df['SYM_NAME'].str.contains("FID", na=False, case=False)&
                ~pcb_df['COMP_VALUE'].str.contains("FID", na=False, case=False)
            ]
             # Log processing statistics before nozzle_feeder_assignments
            self.logger.info(f"Processed {pcb_df} components")

            # Adjust rotation after nozzle assignment
            pcb_df['SYM_ROTATE'] = pcb_df.apply(self.adjust_rotation, axis=1)

            # Rename columns for Neoden4 format
            column_mapping = {
                'Nozzle': 'Type',
                'REFDES': 'Nozzle',
                'COMP_VALUE': 'X',
                'SYM_NAME': 'Y',
                'SYM_X': 'Angle',
                'SYM_Y': 'Footprint',
                'SYM_ROTATE': 'Value',
                'SYM_MIRROR': 'Pick height'
            }
            pcb_df.rename(columns=column_mapping, inplace=True)

            
            self.logger.info(f"Processed {len(pcb_df)} components")
            self.logger.info(f"Applied coordinate transformation with {len(fiducial_info['points_i'])} fiducial points")
            
            # Validate final component positions
            max_x = pcb_df['Angle'].max()
            max_y = pcb_df['Footprint'].max()
            self.logger.info(f"Component position range - X: 0 to {max_x:.2f}, Y: 0 to {max_y:.2f}")

            return pcb_df

        except Exception as e:
            self.logger.error(f"Error processing components: {str(e)}")
            raise PCBProcessingError(f"Failed to process components: {str(e)}")

    def get_fiducial_info(self, n4_df: pd.DataFrame, pcb_df: pd.DataFrame) -> Dict:
        """
        Extract fiducial information from template and PCB data
        
        Args:
            n4_df: Neoden4 template data
            pcb_df: PCB component data
            
        Returns:
            Dictionary containing fiducial information
        """
        try:
            # Get fiducial locations from template
            measured_fiducial_loc = n4_df.loc[n4_df['#Feeder'] == "mark"]
            if measured_fiducial_loc.empty:
                raise PCBProcessingError("No fiducial marks found in template")
                
            col_names = list(measured_fiducial_loc.columns)

            # Get fiducial points from PCB data
            fiducial_pts_i = self.get_board_fiducials(pcb_df)
            if not fiducial_pts_i:
                raise PCBProcessingError("No fiducials found in PCB data")
                
            self.logger.info(f"Found {len(fiducial_pts_i)} fiducials in PCB data")
            for i, pt in enumerate(fiducial_pts_i):
                self.logger.info(f"PCB Fiducial {i+1}: X={pt[0]:.3f}, Y={pt[1]:.3f}")

            # Get template fiducial points
            fiducial_pts_m = []
            try:
                for i in range(len(fiducial_pts_i)):
                    x = float(measured_fiducial_loc[col_names[i*2+3]].iloc[0])
                    y = float(measured_fiducial_loc[col_names[i*2+4]].iloc[0])
                    fiducial_pts_m.append([x, y])
                    self.logger.info(f"Template Fiducial {i+1}: X={x:.3f}, Y={y:.3f}")
            except (IndexError, ValueError) as e:
                raise PCBProcessingError(f"Error extracting template fiducial coordinates: {str(e)}")

            if len(fiducial_pts_i) != len(fiducial_pts_m):
                raise PCBProcessingError(
                    f"Mismatch in number of fiducials: PCB has {len(fiducial_pts_i)}, "
                    f"Template has {len(fiducial_pts_m)}"
                )

            # Sort fiducial points by distance from origin (0,0)
            fiducial_pts_mr = sorted(
                fiducial_pts_m, 
                key=lambda point: math.sqrt(point[0]**2 + point[1]**2)
            )
            self.logger.info(f"FIDUCIALS: TEMPLATE={fiducial_pts_mr}, PCB={fiducial_pts_i}")
            self.logger.info(f"Processed {pcb_df} components")
            print("Measured Fid", fiducial_pts_mr)
            print("PCB Fid", fiducial_pts_i)
            
            # Get offset from first fiducial
            n4_offsetx = fiducial_pts_i[0][0]
            n4_offsety = fiducial_pts_i[0][1]
            
            self.logger.info(f"Using offset point: X={n4_offsetx:.3f}, Y={n4_offsety:.3f}")
                    
            return {
                'offset_x': n4_offsetx,
                'offset_y': n4_offsety,
                'points_i': fiducial_pts_i,
                'points_m': fiducial_pts_mr
            }

        except Exception as e:
            self.logger.error(f"Error in get_fiducial_info: {str(e)}")
            raise PCBProcessingError(f"Failed to get fiducial information: {str(e)}")

    def get_board_fiducials(self, pcb_df: pd.DataFrame) -> List[List[float]]:
        """
        Extract fiducial points from PCB data
        
        Args:
            pcb_df: PCB component data
            
        Returns:
            List of fiducial coordinates [[x1,y1], [x2,y2], ...]
        """
        try:
            # Find fiducials in PCB data
            fid_df = pcb_df[pcb_df['REFDES'].str.contains('FID', case=False, na=False)]
            
            if fid_df.empty:
                self.logger.error("No fiducials found in PCB data")
                return []
                
            # Calculate distance from origin for each fiducial
            fid_df['XY_DIST'] = fid_df.apply(
                lambda row: math.dist([row['SYM_X'], row['SYM_Y']], [0, 0]), 
                axis=1
            )
            
            # Sort by distance
            fid_df.sort_values("XY_DIST", ascending=True, inplace=True)
            
            # Log found fiducials
            self.logger.info(f"Found {len(fid_df)} fiducials:")
            for _, fid in fid_df.iterrows():
                self.logger.info(
                    f"  {fid['REFDES']}: X={fid['SYM_X']:.3f}, Y={fid['SYM_Y']:.3f}, "
                    f"Distance={fid['XY_DIST']:.3f}"
                )
            
            # Return coordinates as list of [x,y] pairs
            fiducials = fid_df[['SYM_X', 'SYM_Y']].values.tolist()
            
            if not fiducials:
                raise PCBProcessingError("No valid fiducial coordinates found")
                
            return fiducials

        except Exception as e:
            self.logger.error(f"Error in get_board_fiducials: {str(e)}")
            raise PCBProcessingError(f"Failed to get board fiducials: {str(e)}")

    def calculate_homography(self, fiducial_pts_i: List[List[float]],
                           fiducial_pts_m: List[List[float]]) -> np.ndarray:
        """Calculate homography transformation matrix"""
        try:
            num_points = len(fiducial_pts_i)
            if num_points < 2:
                raise PCBProcessingError("At least 2 fiducial points required")

            if num_points == 2:
                # Affine transformation for 2 points
                src = np.array(fiducial_pts_i, dtype=np.float32)
                dst = np.array(fiducial_pts_m, dtype=np.float32)
                
                # Calculate translation
                t_x = np.mean(dst[:, 0] - src[:, 0])
                t_y = np.mean(dst[:, 1] - src[:, 1])
                
                # Calculate rotation and scale
                src_centered = src - np.mean(src, axis=0)
                dst_centered = dst - np.mean(dst, axis=0)
                
                covariance = np.dot(src_centered.T, dst_centered)
                U, _, Vt = np.linalg.svd(covariance)
                
                rotation = np.dot(Vt.T, U.T)
                scale = np.sum(dst_centered * np.dot(src_centered, rotation)) / np.sum(src_centered**2)
                
                transform = np.zeros((2, 3))
                transform[:2, :2] = scale * rotation
                transform[:, 2] = [t_x, t_y]
                return transform
            else:
                # Full homography for 3+ points
                A = np.zeros((2*num_points, 9))
                for i in range(num_points):
                    x, y = fiducial_pts_i[i]
                    x_prime, y_prime = fiducial_pts_m[i]
                    A[2*i] = [-x, -y, -1, 0, 0, 0, x*x_prime, y*x_prime, x_prime]
                    A[2*i+1] = [0, 0, 0, -x, -y, -1, x*y_prime, y*y_prime, y_prime]

                _, _, V = np.linalg.svd(A)
                H = V[-1].reshape(3, 3)
                return H / H[2, 2]

        except Exception as e:
            logging.error(f"Error in calculate_homography: {str(e)}")
            raise PCBProcessingError(f"Failed to calculate transformation: {str(e)}")

    def apply_transform(self, pcb_df: pd.DataFrame, 
                       transform: np.ndarray) -> pd.DataFrame:
        """Apply coordinate transformation to components"""
        try:
            for row in pcb_df.itertuples(index=False):
                pt_i = np.array([row.SYM_X, row.SYM_Y])
                if transform.shape == (2, 3):  # Affine
                    pt_f = np.dot(transform[:, :2], pt_i) + transform[:, 2]
                else:  # Homography
                    pt_h = np.array([pt_i[0], pt_i[1], 1])
                    pt_f = np.dot(transform, pt_h)
                    pt_f = pt_f[:2] / pt_f[2]

                pcb_df.loc[pcb_df['REFDES'] == row.REFDES, 'SYM_X'] = pt_f[0]
                pcb_df.loc[pcb_df['REFDES'] == row.REFDES, 'SYM_Y'] = pt_f[1]

            return pcb_df

        except Exception as e:
            logging.error(f"Error in apply_transform: {str(e)}")
            raise PCBProcessingError(f"Failed to apply transformation: {str(e)}")

    def adjust_rotation(self, row: pd.Series) -> float:
        """Adjust component rotation"""
        try:
            rotation = float(row['SYM_ROTATE']) % 360
            if int(row['Feeder ID']) >= 20:
                rotation = (rotation - 180) % 360
            
            if rotation > 180:
                rotation = rotation - 360
            
            return rotation

        except Exception as e:
            logging.error(f"Error in adjust_rotation: {str(e)}")
            return 0.0

    def generate_output(self, processed_df: pd.DataFrame, template_df: pd.DataFrame,
                       input_file: str) -> str:
        """
        Generate final output CSV file
        
        Args:
            processed_df: Processed PCB data
            template_df: Template data
            input_file: Original input file path
            
        Returns:
            Path to generated output file
        """
        try:
            # Combine template and processed data
            frames = [template_df, processed_df]
            final_df = pd.concat(frames)

            # Generate output filename
            output_path = os.path.join(
                os.path.dirname(input_file),
                f'N4_{Path(input_file).stem}.csv'
            )

            # Save to CSV
            final_df.to_csv(output_path, index=False)
            logging.info(f"Generated output file: {output_path}")

            return output_path

        except Exception as e:
            logging.error(f"Error in generate_output: {str(e)}")
            raise PCBProcessingError(f"Failed to generate output file: {str(e)}")

    def validate_input_files(self, pcb_file: str, template_file: str) -> None:
        """
        Validate input files exist and have required format
        
        Args:
            pcb_file: Path to PCB file
            template_file: Path to template file
            
        Raises:
            PCBProcessingError: If validation fails
        """
        # Check file existence
        if not os.path.exists(pcb_file):
            raise PCBProcessingError(f"PCB file not found: {pcb_file}")
        if not os.path.exists(template_file):
            raise PCBProcessingError(f"Template file not found: {template_file}")

        # Check file extensions
        if not pcb_file.lower().endswith('.csv'):
            raise PCBProcessingError(f"Invalid PCB file format: {pcb_file}")
        if not template_file.lower().endswith('.csv'):
            raise PCBProcessingError(f"Invalid template file format: {template_file}")

        # Validate PCB file structure
        try:
            pcb_df = pd.read_csv(pcb_file)
            required_cols = ['REFDES', 'COMP_VALUE', 'SYM_NAME', 'SYM_X', 'SYM_Y', 'SYM_ROTATE', 'SYM_MIRROR']
            missing_cols = [col for col in required_cols if col not in pcb_df.columns]
            if missing_cols:
                raise PCBProcessingError(f"Missing columns in PCB file: {missing_cols}")
        except Exception as e:
            raise PCBProcessingError(f"Failed to read PCB file: {str(e)}")

        # Validate template file structure
        try:
            template_df = pd.read_csv(template_file)
            required_cols = ['#Feeder', 'Feeder ID', 'Nozzle']
            missing_cols = [col for col in required_cols if col not in template_df.columns]
            if missing_cols:
                raise PCBProcessingError(f"Missing columns in template file: {missing_cols}")
        except Exception as e:
            raise PCBProcessingError(f"Failed to read template file: {str(e)}")

    def sort_components(self, pcb_df: pd.DataFrame, sort_config: Dict) -> pd.DataFrame:
        """
        Sort components according to multiple criteria
        
        Args:
            pcb_df: DataFrame containing PCB components
            sort_config: Dictionary containing sorting configuration
            
        Returns:
            Sorted DataFrame
        """
        try:
            if sort_config['columns']:
                # Create list of ascending/descending for each column
                ascending = [sort_config['ascending']] * len(sort_config['columns'])
                
                # Sort DataFrame
                pcb_df.sort_values(
                    by=sort_config['columns'],
                    ascending=ascending,
                    inplace=sort_config['inplace']
                )
                
            return pcb_df
            
        except Exception as e:
            logging.error(f"Error sorting components: {str(e)}")
            raise PCBProcessingError(f"Failed to sort components: {str(e)}")
        
class PCR_File_Splitter:
    def __init__(self, pcr_file: str, component_table_file: str, neoden4_file: str, config_file: str, progress_callback=None):
       
        self.logger = logging.getLogger('PCR_File_Splitter')
        self.progress_callback = progress_callback
        
        self.config = self._load_config(config_file)

        self.pcr_df = pd.read_csv(pcr_file)
        self.component_table_df = pd.read_csv(component_table_file)
        self.neoden4_df = pd.read_csv(neoden4_file)
        self.pcr_filename = Path(pcr_file).stem
        self.filepath = os.path.split(pcr_file)[0]
        
        # Initialize with dynamic reel sizes
        self.available_reel_sizes = set()  # Will be populated from input files
        self.available_reels = {}
        self.available_feeders = {}
        self._initialize_available_feeders()
        self._remove_ignored_features()
        
        self.placed_components = set()
        self.matched_count = 0
        self.unmatched_count = 0
        
        self.logger.info("PCR_File_Splitter initialized")
        self.logger.info(f"Processing PCR file: {pcr_file}")
        
    def update_progress(self, current: int, total: int, status: str):
        """Update progress bar if callback is available"""
        if self.progress_callback:
            self.progress_callback(current, total, status)

    def _initialize_available_feeders(self):
        """Initialize available feeders based on actual reel sizes from template and component table"""
        # Get all unique reel sizes from Component_Table
        component_reel_sizes = set(str(size) for size in self.component_table_df['Reel'].unique())
        
        # Get all unique reel sizes from Neoden4 template
        template_reel_sizes = set(str(size) for size in self.neoden4_df['Reel'].unique() 
                                if str(size).isdigit())  # Exclude non-numeric values like '-'
        
        # Combine all unique reel sizes
        self.available_reel_sizes = component_reel_sizes.union(template_reel_sizes)
        
        # Initialize empty lists for each reel size
        self.available_reels = {size: [] for size in self.available_reel_sizes}
        
        # Track Feeder 20 separately but it's actually an 8mm reel
        self.feeder_20_available = False
        
        # Sort the template by Reel column first
        sorted_template = self.neoden4_df.sort_values('Reel')
        
        # Go through template and assign feeders based on their actual reel size
        for _, row in sorted_template.iterrows():
            if row['#Feeder'] == 'stack':
                feeder_id = str(row['Feeder ID'])
                reel_size = str(row['Reel'])
                
                # Special handling for feeder 20
                if feeder_id == '20':
                    self.feeder_20_available = True
                    continue
                    
                # All other feeders go by their reel size
                if reel_size in self.available_reels:
                    self.available_reels[reel_size].append(feeder_id)
                else:
                    self.logger.warning(f"Unknown reel size {reel_size} for feeder {feeder_id}")
        
        # Sort feeders numerically within each reel size
        for reel_size in self.available_reels:
            self.available_reels[reel_size].sort(key=lambda x: int(x))
        
        self.logger.info("Available reel sizes: %s", sorted(self.available_reel_sizes))
        self.logger.info("Available feeders after initialization:")
        for reel_size, feeders in self.available_reels.items():
            self.logger.info(f"Reel {reel_size}: {feeders}")
        self.logger.info(f"Feeder 20 available: {self.feeder_20_available}")

    def _reset_available_feeders(self):
        """Reset available feeders to their initial state based on template"""
        # Reset all reel sizes to empty lists
        self.available_reels = {size: [] for size in self.available_reel_sizes}
        
        # Reset Feeder 20 availability
        self.feeder_20_available = False
        
        # Sort the template by Reel column first
        sorted_template = self.neoden4_df.sort_values('Reel')
        
        # Reconstruct the feeder assignments
        for _, row in sorted_template.iterrows():
            if row['#Feeder'] == 'stack':
                feeder_id = str(row['Feeder ID'])
                reel_size = str(row['Reel'])
                
                # Special handling for feeder 20
                if feeder_id == '20':
                    self.feeder_20_available = True
                    continue
                    
                # All other feeders go by their reel size
                if reel_size in self.available_reels:
                    self.available_reels[reel_size].append(feeder_id)
        
        # Sort feeders numerically within each reel size
        for reel_size in self.available_reels:
            self.available_reels[reel_size].sort(key=lambda x: int(x))

    def _get_reel_progression(self, initial_reel: str) -> List[str]:
        """
        Get progression of compatible reel sizes for a given initial reel size
        
        Args:
            initial_reel: Initial reel size as string
            
        Returns:
            List of compatible reel sizes in ascending order
        """
        try:
            # Convert available reel sizes to integers for sorting
            sorted_sizes = sorted([int(size) for size in self.available_reel_sizes])
            
            # Find starting point in progression
            try:
                start_index = sorted_sizes.index(int(initial_reel))
            except ValueError:
                self.logger.error(f"Invalid initial reel size: {initial_reel}")
                return []
                
            # Return progression from initial size onwards
            progression = [str(size) for size in sorted_sizes[start_index:]]
            
            self.logger.debug(f"Reel progression for {initial_reel}: {progression}")
            return progression
            
        except Exception as e:
            self.logger.error(f"Error in _get_reel_progression: {str(e)}")
            return []

    def _remove_ignored_features(self):
        ignored_features = self.config['ignored_pcb_features']
        ignored_features.extend(['TP', 'DNP', 'DNE', 'HDR', 'Hole', 'Panel', 'Edge', 'MH', 'MOUNTHOLE'])
        self.pcr_df = self.pcr_df[
            ~self.pcr_df['REFDES'].str.contains('|'.join(ignored_features), na=False, case=False) &
            ~self.pcr_df['SYM_NAME'].str.contains('|'.join(ignored_features), na=False, case=False) &
            ~self.pcr_df['COMP_VALUE'].str.contains('|'.join(ignored_features), na=False, case=False)
        ]

    def process_files(self):
        try:
            pcr_groups = self._group_pcr_data()
            for group_name, pcr_data in pcr_groups.items():
                self.logger.info(f"Processing group: {group_name}")
                self._process_group(pcr_data, group_name)
                #time.sleep(1)
        except Exception as e:
            self.logger.error(f"An error occurred during processing: {str(e)}", exc_info=True)
            raise

    def _create_component_groups(self, pcr_data: pd.DataFrame) -> List[Dict]:
        """Create component groups with accurate counting"""
        component_groups = defaultdict(list)
        component_counts = defaultdict(int)
        
        # First pass: Count all components
        for _, pcr_row in pcr_data.iterrows():
            group_key = (pcr_row['SYM_NAME'], pcr_row['COMP_VALUE'])
            component_counts[group_key] += 1
        
        # Second pass: Create groups with known counts
        for _, pcr_row in pcr_data.iterrows():
            comp_match = self._find_component_match(pcr_row)
            group_key = (pcr_row['SYM_NAME'], pcr_row['COMP_VALUE'])
            
            component_groups[group_key].append({
                'footprint': pcr_row['SYM_NAME'],
                'value': pcr_row['COMP_VALUE'],
                'Reel': comp_match['Reel'] if comp_match else None,
                'pcr_row': pcr_row,
                'matched': comp_match is not None
            })
        
        # Convert to list format with accurate counts
        result = [
            {
                'footprint': key[0],
                'value': key[1],
                'Reel': group[0]['Reel'],
                'components': group,
                'count': component_counts[key]  # Use pre-calculated count
            }
            for key, group in component_groups.items()
        ]
        
        # Log component counts for verification
        for group in result:
            self.logger.info(f"Component group {group['footprint']}/{group['value']} count: {group['count']}")
            
        return result

    def _sort_component_groups(self, groups: List[Dict]) -> List[Dict]:
        """Sort component groups by count in descending order"""
        sorted_groups = sorted(groups, key=lambda x: x['count'], reverse=True)
        self.logger.info("Sorted groups order:")
        for group in sorted_groups:
            self.logger.info(f"{group['footprint']}/{group['value']}: {group['count']} placements")
        return sorted_groups

    def _find_component_match(self, pcr_row: pd.Series) -> Optional[Dict]:
        comp_matches = self.component_table_df[self.component_table_df['Footprint'] == pcr_row['SYM_NAME']]
        if not comp_matches.empty:
            match = comp_matches.iloc[0]
            self.logger.info(f"Match found for {pcr_row['SYM_NAME']}/{pcr_row['COMP_VALUE']} in component table")
            return {
                'footprint': match['Footprint'],
                'value': pcr_row['COMP_VALUE'],
                'Reel': str(match['Reel'])  # Ensure Reel is converted to string
            }
        else:
            self.logger.warning(f"No match found for {pcr_row['SYM_NAME']}/{pcr_row['COMP_VALUE']} in component table")
        return None

    def _place_component(self, template: pd.DataFrame, component: Dict) -> Tuple[PlacementResult, Optional[str], Optional[str]]:
        component_key = f"{component['footprint']}/{component['value']}"
        
        if 'Reel' not in component:
            self.logger.warning(f"No reel information for component {component_key}")
            return PlacementResult.NOT_PLACED, None, None
        
        reel_sizes = ['8', '12', '16', '20']
        initial_reel = component['Reel']
        
        # Check if the component is already placed in the template
        already_placed_rows = template[(template['Footprint'] == component['footprint']) & 
                                    (template['Value'] == component_key)]
        if not already_placed_rows.empty:
            self.logger.info(f"Component {component_key} is already placed in the template")
            return PlacementResult.ALREADY_PLACED, initial_reel, already_placed_rows.iloc[0]['#Feeder']
        
        for reel in reel_sizes[reel_sizes.index(initial_reel):]:
            self.logger.debug(f"Attempting to place component {component_key} with reel {reel}")
            
            if reel in self.available_reels and self.available_reels[reel]:
                for feeder_index, feeder in enumerate(self.available_reels[reel]):
                    vacant_rows = template[(template['Reel'] == reel) & (template['#Feeder'] == feeder) & (template['Footprint'] == '-')]
                    if not vacant_rows.empty:
                        row_index = vacant_rows.index[0]
                        self._merge_component_data(template, row_index, component)
                        # Remove the used feeder only after successful placement
                        self.available_reels[reel].pop(feeder_index)
                        self.logger.info(f"Placed component {component_key} using feeder {feeder} (reel {reel})")
                        return PlacementResult.PLACED, reel, feeder
            else:
                self.logger.warning(f"No available feeders for reel {reel} for component {component_key}")
        
        self.logger.warning(f"No vacant positions found for component {component_key} on any available reel")
        return PlacementResult.NOT_PLACED, None, None

    def _merge_component_group_data(self, template: pd.DataFrame, row_index: int, group: Dict):
        """Update template row with component data while preserving nozzle value"""
        try:
            # Get the feeder ID for this row
            feeder_id = template.at[row_index, 'Feeder ID']
            
            # Get the original nozzle value from base template
            original_nozzle = self.neoden4_df[
                (self.neoden4_df['#Feeder'] == 'stack') & 
                (self.neoden4_df['Feeder ID'] == feeder_id)
            ]['Nozzle'].iloc[0]
            
            # Get component data from component table
            comp_data = self.component_table_df[
                self.component_table_df['Footprint'] == group['footprint']
            ].iloc[0]
            
            # Update template row
            template.at[row_index, 'Footprint'] = group['footprint']
            template.at[row_index, 'Value'] = f"{group['footprint']}/{group['value']}"
            template.at[row_index, 'Nozzle'] = original_nozzle  # Preserve original nozzle value
            
            # Copy parameters from component table
            template.at[row_index, 'Pick height'] = comp_data['Pick height']
            template.at[row_index, 'Pick delay'] = comp_data['Pick delay']
            template.at[row_index, 'Place Height'] = comp_data['Place Height']
            template.at[row_index, 'Place Delay'] = comp_data['Place Delay']
            template.at[row_index, 'Vacuum detection'] = comp_data['Vacuum detection']
            template.at[row_index, 'Threshold'] = comp_data['Threshold']
            template.at[row_index, 'Vision Alignment'] = comp_data['Vision Alignment']
            template.at[row_index, 'Speed'] = comp_data['Speed']
            
            # Copy unnamed parameters
            for i in range(17, 30):
                col_name = f'Unnamed: {i}'
                if col_name in comp_data:
                    template.at[row_index, col_name] = comp_data[col_name]
            
            self.logger.debug(
                f"Updated template row {row_index} with component "
                f"{group['footprint']}/{group['value']} using original nozzle {original_nozzle}"
            )
            
        except Exception as e:
            self.logger.error(f"Error merging component data for {group['footprint']}: {str(e)}")
            raise

    def _merge_component_data(self, template: pd.DataFrame, row_index: int, component: Dict):
        # Get the component data from the component table
        comp_data = self.component_table_df[self.component_table_df['Footprint'] == component['footprint']].iloc[0]
        
        # Update all columns except 'Reel'
        for column in template.columns:
            if column in comp_data.index and column != 'Reel':
                template.at[row_index, column] = comp_data[column]
        
        # Update Footprint and Value separately as they might have special formatting
        template.at[row_index, 'Footprint'] = component['footprint']
        template.at[row_index, 'Value'] = f"{component['footprint']}/{component['value']}"
        
        self.logger.info(f"Updated template row {row_index} with component {component['footprint']}/{component['value']}")
    
    def _save_pcr(self, pcr_data: pd.DataFrame, suffix: str):
        filename = f"{self.pcr_filename}{suffix}.csv"
        pcr_data.to_csv(os.path.join(self.filepath, filename), index=False)
        self.logger.info(f"Saved {filename}")

    def _group_pcr_data(self) -> Dict[str, pd.DataFrame]:
        grouped = {'_Bot': self.pcr_df[self.pcr_df['SYM_MIRROR'] == 'YES'],
            '_Top': self.pcr_df[self.pcr_df['SYM_MIRROR'] == 'NO']}
        
        for group, data in grouped.items():
            self.logger.info(f"Group {group} has {len(data)} components")
            if len(data) == 0:
                self.logger.warning(f"Group {group} is empty. Check PCR data for SYM_MIRROR values.")
        
        return grouped

    def _is_fiducial(self, pcr_row: pd.Series) -> bool:
        return pcr_row['REFDES'].startswith('FID')

    def _save_template(self, template: pd.DataFrame, suffix: str):
        # Remove the 'Reel' column
        template_to_save = template.drop(columns=['Reel'], errors='ignore')
        filename = f"Neoden4_Template{self.pcr_filename}{suffix}.csv"
        template_to_save.to_csv(os.path.join(self.filepath, filename), index=False)
        self.logger.info(f"Saved {filename}.csv (Reel column removed)")

    def _save_manual_placement(self, manual_placement: pd.DataFrame, group_name: str):
        filename = f"Manual_Placement{group_name}.csv"
        manual_placement.to_csv(os.path.join(self.filepath, filename), index=False)
        self.logger.info(f"Saved {filename}")

    def _get_reel_options(self, component_size: str) -> List[str]:
        sizes = ['8', '12', '16']
        try:
            start_index = sizes.index(str(component_size))
        except ValueError:
            self.logger.warning(f"Invalid component size: {component_size}. Using smallest size.")
            start_index = 0

        reel_options = []
        for size in sizes[start_index:]:
            reel_options.extend(list(self.available_reels[size]))
            if reel_options:
                break
        
        return reel_options
    
    def _log_available_reels(self):
        self.logger.info("Current state of available reels:")
        for size, reels in self.available_reels.items():
            self.logger.info(f"Size {size}: {len(reels)} reels available")
            self.logger.debug(f"Size {size} reels: {reels}")   

    def _remove_ignored_features(self):
        ignored_features = self.config['ignored_pcb_features']
        ignored_features.extend(['TP', 'DNP', 'DNE', 'HDR', 'Hole', 'Panel', 'Edge', 'MH', 'MOUNTHOLE'])
        self.pcr_df = self.pcr_df[
            ~self.pcr_df['REFDES'].str.contains('|'.join(ignored_features), na=False, case=False) &
            ~self.pcr_df['SYM_NAME'].str.contains('|'.join(ignored_features), na=False, case=False) &
            ~self.pcr_df['COMP_VALUE'].str.contains('|'.join(ignored_features), na=False, case=False)
        ]
    
    def _report_matching_stats(self):
        total = self.matched_count + self.unmatched_count
        self.logger.info(f"Matching Statistics:")
        self.logger.info(f"Total components: {total}")
        self.logger.info(f"Matched components: {self.matched_count} ({self.matched_count/total*100:.2f}%)")
        self.logger.info(f"Unmatched components: {self.unmatched_count} ({self.unmatched_count/total*100:.2f}%)")

    def _load_config(self, config_file: str) -> Dict:
        with open(config_file, 'r') as f:
            if config_file.endswith('.json'):
                return json.load(f)
            elif config_file.endswith('.yaml') or config_file.endswith('.yml'):
                return yaml.safe_load(f)
            else:
                raise ValueError("Unsupported configuration file format")

    def _setup_logger(self) -> logging.Logger:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        logger = logging.getLogger('PCR_File_Splitter')
        logger.setLevel(self.config['logging']['level'])
        
        formatter = logging.Formatter(self.config['logging']['format'])
        
        file_handler = logging.FileHandler(self.config['logging']['file'])
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger

    def _should_skip_component(self, pcr_row: pd.Series) -> bool:
        return any(feature in pcr_row['REFDES'] or feature in pcr_row['SYM_NAME'] 
                   for feature in self.config['ignored_pcb_features'])

    def _process_group(self, pcr_data: pd.DataFrame, group_name: str):
        """Process a group of PCR data with smart feeder assignment"""
        try:
            # Initialize dataframes
            manual_placement = pd.DataFrame(columns=pcr_data.columns)
            fiducials = pd.DataFrame(columns=pcr_data.columns)
            template_a = self.neoden4_df.copy()  # Create exact copy of base template
            template_b = self.neoden4_df.copy()
            pcr_a = pd.DataFrame(columns=pcr_data.columns)
            pcr_b = pd.DataFrame(columns=pcr_data.columns)

            # Create component groups and sort by count
            if self.progress_callback:
                self.progress_callback(10, 100, f"Creating component groups for {group_name}")
                
            component_groups = self._create_component_groups(pcr_data)
            
            # Split groups by count
            low_count_groups = []
            high_count_groups = []
            
            for group in component_groups:
                if group['count'] <= FEEDER_20_MAX_COUNT:
                    low_count_groups.append(group)
                else:
                    high_count_groups.append(group)
                    
            # Sort groups
            high_count_groups.sort(key=lambda x: x['count'], reverse=True)
            low_count_groups.sort(key=lambda x: x['count'], reverse=True)
            
            if self.progress_callback:
                self.progress_callback(20, 100, 
                    f"Sorted components - {len(high_count_groups)} high count, {len(low_count_groups)} low count groups")

            # Process components in sorted order
            total_groups = len(low_count_groups) + len(high_count_groups)
            current_group = 0

            # First process high count groups
            self.logger.info("Processing high count groups first...")
            for group in high_count_groups:
                if self.progress_callback:
                    progress = 20 + int((current_group / total_groups) * 60)
                    self.progress_callback(progress, 100, 
                        f"Processing high count group {group['footprint']}/{group['value']} (count: {group['count']})")
            
                # Try placement in templates
                for template, pcr_df in [(template_a, pcr_a), (template_b, pcr_b)]:
                    self._reset_available_feeders()
                    result, reel, feeder = self._place_component_group(template, group, allow_feeder_20=False)
                    
                    if result in [PlacementResult.PLACED, PlacementResult.ALREADY_PLACED]:
                        components_df = pd.DataFrame([c['pcr_row'].to_dict() for c in group['components']])
                        if pcr_df is pcr_a:
                            pcr_a = pd.concat([pcr_a, components_df], ignore_index=True)
                        else:
                            pcr_b = pd.concat([pcr_b, components_df], ignore_index=True)
                        
                        self.matched_count += group['count']
                        placed = True
                        self.logger.info(f"Placed high count group {group['footprint']}/{group['value']} "
                                    f"(count: {group['count']}) on feeder {feeder}")
                        break
                        
                if result == PlacementResult.NOT_PLACED:
                    manual_placement = pd.concat([manual_placement, pd.DataFrame(
                        c['pcr_row'].to_dict() for c in group['components'])], ignore_index=True)
                    self.unmatched_count += group['count']
                    self.logger.warning(f"Could not place high count group {group['footprint']}/{group['value']} "
                                    f"(count: {group['count']})")
                    
                current_group += 1

            # Process low count groups
            self.logger.info("Processing low count groups...")
            for group in low_count_groups:
                if self.progress_callback:
                    progress = 20 + int((current_group / total_groups) * 60)
                    self.progress_callback(progress, 100, 
                        f"Processing low count group {group['footprint']}/{group['value']} (count: {group['count']})")
                
                # Handle fiducials
                if self._is_fiducial(group['components'][0]['pcr_row']):
                    fiducials = pd.concat([fiducials, pd.DataFrame(
                        c['pcr_row'].to_dict() for c in group['components'])], ignore_index=True)
                    current_group += 1
                    continue

                # Try placement in templates
                for template, pcr_df in [(template_a, pcr_a), (template_b, pcr_b)]:
                    self._reset_available_feeders()
                    result, reel, feeder = self._place_component_group(template, group, allow_feeder_20=True)
                    
                    if result in [PlacementResult.PLACED, PlacementResult.ALREADY_PLACED]:
                        components_df = pd.DataFrame([c['pcr_row'].to_dict() for c in group['components']])
                        if pcr_df is pcr_a:
                            pcr_a = pd.concat([pcr_a, components_df], ignore_index=True)
                        else:
                            pcr_b = pd.concat([pcr_b, components_df], ignore_index=True)
                        
                        self.matched_count += group['count']
                        action_word = "Found" if result == PlacementResult.ALREADY_PLACED else "Placed"
                        self.logger.info(f"{action_word} {group['count']} components of "
                            f"{group['footprint']}/{group['value']} in Template{group_name}"
                            f"{'a' if pcr_df is pcr_a else 'b'} using reel {reel}, feeder {feeder}")
                        break

                if result == PlacementResult.NOT_PLACED:
                    manual_placement = pd.concat([manual_placement, pd.DataFrame(
                        c['pcr_row'].to_dict() for c in group['components'])], ignore_index=True)
                    self.unmatched_count += group['count']
                    self.logger.warning(f"Could not place low count group {group['footprint']}/{group['value']} "
                                    f"(count: {group['count']})")
                    
                current_group += 1

            # Add fiducials and save files
            if self.progress_callback:
                self.progress_callback(80, 100, f"Adding fiducials and saving files for {group_name}")
                
            pcr_a = pd.concat([pcr_a, fiducials], ignore_index=True)
            pcr_b = pd.concat([pcr_b, fiducials], ignore_index=True)
            
            self._save_template(template_a, f"{group_name}a")
            self._save_template(template_b, f"{group_name}b")
            self._save_pcr(pcr_a, f"{group_name}a")
            self._save_pcr(pcr_b, f"{group_name}b")
            self._save_manual_placement(manual_placement, group_name)

            if self.progress_callback:
                self.progress_callback(100, 100, f"Completed processing {group_name}")

            self._log_placement_statistics(group_name, template_a, template_b, 
                                        manual_placement, fiducials)
                
        except Exception as e:
            self.logger.error(f"Error in _process_group: {str(e)}", exc_info=True)
            raise

    def _place_component_group(self, template: pd.DataFrame, group: Dict, 
                            allow_feeder_20: bool = True) -> Tuple[PlacementResult, Optional[str], Optional[str]]:
        """Place a component group in the template with proper reel size and feeder restrictions"""
        component_key = f"{group['footprint']}/{group['value']}"
        count = group['count']
        
        self.logger.info(f"Attempting to place {component_key} with count {count}, allow_feeder_20={allow_feeder_20}")
        
        if not group.get('Reel'):
            self.logger.warning(f"No reel information for component group {component_key}")
            return PlacementResult.NOT_PLACED, None, None
        
        # Get the initial reel size for this component
        initial_reel = str(group['Reel'])
        
        self.logger.info(f"Initial reel size for {component_key}: {initial_reel}")
        
        # If component requires 8mm reel and Feeder 20 is available and allowed
        if initial_reel == '8' and self.feeder_20_available and allow_feeder_20 and count <= FEEDER_20_MAX_COUNT:
            # Try Feeder 20 first for eligible components
            self.logger.debug(f"Checking Feeder 20 for {component_key}")
            vacant_rows = template[
                (template['Reel'] == '8') & 
                (template['Feeder ID'] == '20') & 
                (template['Footprint'] == '-')
            ]
            if not vacant_rows.empty:
                row_index = vacant_rows.index[0]
                if not self._is_duplicate_in_template(template, group['footprint'], group['value']):
                    self._merge_component_group_data(template, row_index, group)
                    self.feeder_20_available = False
                    self.logger.info(f"Placed low-count component {component_key} on Feeder 20")
                    return PlacementResult.PLACED, '8', '20'
        
        # Get allowed reel sizes for this component
        allowed_reels = self._get_reel_progression(initial_reel)
        if not allowed_reels:
            return PlacementResult.NOT_PLACED, None, None
            
        # Try each possible reel size
        for reel in allowed_reels:
            # Skip reel 20 if not allowed or component count too high
            if reel == '20':
                if not allow_feeder_20:
                    self.logger.info(f"Skipping reel 20 - not allowed for {component_key}")
                    continue
                if count > FEEDER_20_MAX_COUNT:
                    self.logger.info(f"Skipping reel 20 - count {count} > FEEDER_20_MAX_COUNT for {component_key}")
                    continue
            
            # Get available feeders for this reel size
            available_feeders = self.available_reels.get(reel, [])
            if not available_feeders:
                self.logger.debug(f"No available feeders for reel size {reel}")
                continue
                
            # Try each available feeder
            for feeder_index, feeder_id in enumerate(available_feeders):
                self.logger.debug(f"Checking feeder {feeder_id} on reel {reel} for {component_key}")
                
                # Look for vacant position in template
                vacant_rows = template[
                    (template['Reel'] == reel) & 
                    (template['Feeder ID'] == feeder_id) & 
                    (template['Footprint'] == '-')
                ]
                
                if not vacant_rows.empty:
                    row_index = vacant_rows.index[0]
                    
                    # Check if component is already placed
                    if self._is_duplicate_in_template(template, group['footprint'], group['value']):
                        self.logger.info(f"Component {component_key} already exists in template")
                        return PlacementResult.ALREADY_PLACED, reel, feeder_id
                    
                    # Place the component
                    self._merge_component_group_data(template, row_index, group)
                    
                    # Remove the used feeder from available feeders
                    self.available_reels[reel].pop(feeder_index)
                    
                    self.logger.info(
                        f"Placed component group {component_key} "
                        f"(count: {count}) using feeder {feeder_id} on reel {reel}"
                    )
                    return PlacementResult.PLACED, reel, feeder_id
                
                self.logger.debug(f"No vacant position for feeder {feeder_id}")
        
        self.logger.warning(
            f"Could not place component group {component_key} "
            f"(count: {count}) on any available feeder"
        )
        return PlacementResult.NOT_PLACED, None, None

    def _log_placement_statistics(self, group_name: str, template_a: pd.DataFrame, 
                                template_b: pd.DataFrame, manual_placement: pd.DataFrame, 
                                fiducials: pd.DataFrame) -> None:
        """Log detailed placement statistics"""
        feeder_20_components = len(template_a[template_a['Feeder ID'] == '20']) + \
                            len(template_b[template_b['Feeder ID'] == '20'])
        
        self.logger.info(f"Group {group_name} processing complete:")
        self.logger.info(f"  Components in {group_name}a: {len(template_a)}")
        self.logger.info(f"  Components in {group_name}b: {len(template_b)}")
        self.logger.info(f"  Components in manual_placement: {len(manual_placement)}")
        self.logger.info(f"  Fiducials: {len(fiducials)}")
        self.logger.info(f"  Components assigned to Feeder #20: {feeder_20_components}")
        self.logger.info(f"  Total matched components: {self.matched_count}")
        self.logger.info(f"  Total unmatched components: {self.unmatched_count}")

    def _is_duplicate_in_template(self, template: pd.DataFrame, footprint: str, value: str) -> bool:
        return ((template['Footprint'] == footprint) & (template['Value'] == f"{footprint}/{value}")).any()

# Initialize application
if __name__ == "__main__":
    app = N4SortGUIApp("Neoden4 CSV Creator v2j", (545, 600))
