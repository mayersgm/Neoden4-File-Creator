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