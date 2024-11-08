# Neoden4 File Creator User Guide

## Overview
The Neoden4 File Creator is a tool for preparing PCB assembly files for use with Neoden4 pick-and-place machines. It processes PCR (Place Component Report) files into the necessary formats for both top and bottom assembly.

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
```
Neoden4Assembly/
├── PCB_Assembly/
│   └── BoardName/
│       └── BOARD_NAME.csv
├── pcr_files/
│   ├── Component_Table.csv
│   ├── Neoden4.csv
│   └── configuration.json
└── N4_CSV_Creator_v2a.py
```

## Step-by-Step Instructions

### 1. PCR File Preparation
1. Export your Allegro PCR file as a CSV file
2. Create a new directory under `/Neoden4Assembly/PCB_Assembly/` with your board name
3. Save the CSV file in this directory: i.e `/Neoden4Assembly/PCB_Assembly/BoardName/BoardName'
4. **Important**: Open the CSV file and rename fiducial reference designators to FID1, FID2, etc.
5. Save and close the file

### 2. Launch Application
1. Important Change file paths at the following line locations:76, 790 and 1133
2. Depending on your os you may need to change the screen size on line 3000 
```bash
python3 N4_CSV_Creator_v2i.py
```

### 3. PCR File Splitting
1. Click the "Split PCR" button
2. Navigate to and select your PCR CSV file
3. The tool will generate several files:
   - Board assembly files:
     * `BOARD_Topa.csv`
     * `BOARD_Topb.csv`
     * `BOARD_Bota.csv`
     * `BOARD_Botb.csv`
   - Template files:
     * `Neoden4_TemplateBOARD_Topa.csv`
     * `Neoden4_TemplateBOARD_Topb.csv`
     * `Neoden4_TemplateBOARD_Bota.csv`
     * `Neoden4_TemplateBOARD_Botb.csv`
   - Manual placement files:
     * `Manual_Placement_Top.csv`
     * `Manual_Placement_Bot.csv`

### 4. Machine Calibration
1. Place board on the Neoden4 machine
2. Upload appropriate template file (Bota or Topa) via USB
3. Use board fiducials to calibrate machine
4. Save modified template with calibration data
5. Export modified template to USB
6. Copy modified template back to your board directory, replacing the original

### 5. Generate Placement File
1. In the GUI, open the matching board file (`BOARD_Topa.csv` or `BOARD_Bota.csv`)
   - The matching template should be automatically selected
   - **For bottom assembly**: Enter the correct board width
2. Select your preferred sorting options:
   - Sort by Reference Designator
   - Sort by XY Location
   - Sort by Component Value
   - Sort by Component Package
3. Click "Generate CSV" button
4. The tool will create `N4_BOARD_Topx.csv` or `N4_BOARD_Botx.csv`

### 6. Component Management
- Components not matching the Component Table will be moved to Manual_Placement file
- Update Component Table (`/Neoden4Assembly/pcr_files/Component_Table.csv`) to include:
  - Component footprint
  - Reel size
  - Component specifications

## Common Issues and Solutions

### Value Variations
    Components that may need standardization:

    Resistors:
    ✓ Correct: 10K
    ✗ Fix: 10k, 10 kOhm, 10 KOhm

    Other Components:
    ✓ Correct: 100 Ohm
    ✗ Fix: 100, 100 OHM, 100Ω

### Troubleshooting Tips
1. Verify fiducial naming (FID1, FID2, etc.)
2. Check board width for bottom assembly
3. Ensure Component Table entries match your PCR file format
4. Verify template file matches selected board side

 ## Component Table Format
    Required format:
    Reel    Footprint	      Value	             Pick height	    Pick delay	    Place Height	    Place Delay  .....
    8	CAP0603	    Footprint/Value	    2.8	            100	                        3                   100	     ......... 
    8	CAP0402	    Footprint/Value	    2.1	            100                         2.7                 100	     .........
    8	RES0603	    Footprint/Value	    2.2	            100                         2.6                 100	     .........	
    8	SOD-123	    Footprint/Value	    2.1	            100	                        3.1                 100	     .........	


## Best Practices
1. Maintain consistent component value formatting
2. Regularly update Component Table
3. Verify fiducial recognition before generating files
4. Back up template files before machine calibration
5. Double-check board width measurements


## Support Files
    Required files in pcr_files directory:
    - Component_Table.csv
    - Neoden4.csv
    - configuration.json"""
