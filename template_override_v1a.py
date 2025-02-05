import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
import pandas as pd
import os
import logging
from datetime import datetime

class Template_Override:
    def __init__(self, root):
        self.root = root
        self.root.title("Template Override_v1a")
        self.base_file_path = None
        self.second_file_path = None
        self.logger = self.setup_logger()
        self.setup_gui()
        
    def setup_logger1(self):
        logger = logging.getLogger('TemplateOverride')
        logger.setLevel(logging.INFO)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        fh = logging.FileHandler(f'template_override_{timestamp}.log')
        fh.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger

    def setup_logger(self):
        # Create logger
        logger = logging.getLogger('TemplateOverride')
        logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Create log file with timestamp in logs directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = os.path.join(log_dir, f'template_override_{timestamp}.log')
        
        # Create file handler
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(fh)
        
        # Log the startup
        logger.info(f"Log file created: {log_file}")
        
        return logger
        

    def setup_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # File selection frame
        file_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="5")
        file_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(file_frame, text="Step 1: Select Base Template", foreground="blue").grid(row=0, column=0, columnspan=2, sticky=tk.W)
        ttk.Button(file_frame, text="Select Base File", command=self.select_base_file).grid(row=1, column=0, pady=5)
        self.base_file_label = ttk.Label(file_frame, text="No file selected")
        self.base_file_label.grid(row=1, column=1, padx=5)
        
        ttk.Label(file_frame, text="Step 2: Select Second Template", foreground="blue").grid(row=2, column=0, columnspan=2, sticky=tk.W)
        ttk.Button(file_frame, text="Select Second File", command=self.select_second_file).grid(row=3, column=0, pady=5)
        self.second_file_label = ttk.Label(file_frame, text="No file selected")
        self.second_file_label.grid(row=3, column=1, padx=5)
        
        ttk.Button(file_frame, text="Process Files", command=self.process_files).grid(row=4, column=0, columnspan=2, pady=10)
        
        self.status_label = ttk.Label(file_frame, text="")
        self.status_label.grid(row=5, column=0, columnspan=2)
        
        # Log display frame
        log_frame = ttk.LabelFrame(main_frame, text="Processing Log", padding="5")
        log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=60, height=10)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        text_handler = TextHandler(self.log_text)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        self.logger.addHandler(text_handler)

    def select_base_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")],
            title="Select Base Template"
        )
        if filepath:
            self.base_file_path = filepath
            self.base_file_label.config(text=os.path.basename(filepath))
            self.logger.info(f"Base template selected: {filepath}")

    def select_second_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv")],
            title="Select Second Template"
        )
        if filepath:
            self.second_file_path = filepath
            self.second_file_label.config(text=os.path.basename(filepath))
            self.logger.info(f"Second template selected: {filepath}")

    def process_files(self):
        if not self.base_file_path or not self.second_file_path:
            msg = "Please select both files first"
            self.status_label.config(text=msg)
            self.logger.warning(msg)
            messagebox.showwarning("Validation Error", msg)
            return

        try:
            self.logger.info("Starting file processing")
            
            # Read CSV files
            df1 = pd.read_csv(self.base_file_path, dtype=str, keep_default_na=False)
            df2 = pd.read_csv(self.second_file_path, dtype=str, keep_default_na=False)
            
            # Split into stack and non-stack rows
            df1_stack = df1[df1['#Feeder'] == 'stack'].copy()
            df2_stack = df2[df2['#Feeder'] == 'stack'].copy()
            preserve_rows = df1[df1['#Feeder'] != 'stack'].copy()
            
            # Convert second file components to list
            available_components = df2_stack.to_dict('records')
            matched_components = set()  # Track which components from file2 have been used
            
            # Lists to track results and replacements
            result_rows = []
            replacement_rows = []  # Track replacements for the new file
            match_count = 0
            fill_count = 0
            
            # First pass: Identify matches and keep them
            for idx, base_row in df1_stack.iterrows():
                new_row = base_row.copy()
                match_found = False
                replacement_row = base_row.copy()  # Create empty row for replacement tracking
                
                # Only look for match if position has component
                if base_row['Footprint'].strip() not in ['-', ''] and base_row['Value'].strip() not in ['-', '']:
                    for i, comp in enumerate(available_components):
                        if (i not in matched_components and
                            comp['Footprint'] == base_row['Footprint'] and 
                            comp['Value'] == base_row['Value']):
                            match_found = True
                            matched_components.add(i)
                            match_count += 1
                            self.logger.info(f"Matched at Feeder ID {base_row['Feeder ID']}: {base_row['Footprint']} - {base_row['Value']}")
                            # Clear replacement row for matched components
                            for col in df1.columns[7:]:
                                replacement_row[col] = ''
                            break
                
                # If no match found, this position needs filling
                if not match_found:
                    # Get next unused component
                    for i, comp in enumerate(available_components):
                        if i not in matched_components:
                            # Update component data from Footprint onwards
                            for col in df1.columns[7:]:
                                new_row[col] = comp[col]
                                replacement_row[col] = comp[col]  # Track the replacement
                            matched_components.add(i)
                            fill_count += 1
                            self.logger.info(f"Filled position at Feeder ID {base_row['Feeder ID']} with: {comp['Footprint']} - {comp['Value']}")
                            break
                else:
                    # Clear replacement row for matched components
                    for col in df1.columns[7:]:
                        replacement_row[col] = ''
                
                result_rows.append(new_row)
                replacement_rows.append(replacement_row)
            
            # Create main result dataframe
            stack_df = pd.DataFrame(result_rows)
            result_df = pd.concat([stack_df, preserve_rows], ignore_index=True)
            
            # Create replacement tracking dataframe
            replacement_df = pd.DataFrame(replacement_rows)
            replacement_df = pd.concat([replacement_df, preserve_rows], ignore_index=True)
            
            # Save main result
            output_path = os.path.join(os.path.dirname(self.second_file_path), 
                                     'template_override_' + os.path.basename(self.second_file_path))
            result_df.to_csv(output_path, index=False)
            
            # Save replacement tracking file
            replacement_path = os.path.join(os.path.dirname(self.second_file_path), 
                                          'Component_Replacements.csv')
            replacement_df.to_csv(replacement_path, index=False)
            
            self.logger.info(f"Matches (kept original): {match_count}")
            self.logger.info(f"Positions filled: {fill_count}")
            self.logger.info(f"Output files saved: \n{os.path.basename(output_path)}\n{os.path.basename(replacement_path)}")
            msg = f"Processing complete\nMatches: {match_count}\nFilled: {fill_count}"
            self.status_label.config(text=msg)
            
        except Exception as e:
            error_msg = f"Error during processing: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.status_label.config(text=error_msg)
            messagebox.showerror("Error", error_msg)


class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)
        self.text_widget.after(0, append)

if __name__ == "__main__":
    root = tk.Tk()
    app = Template_Override(root)
    root.mainloop()
