# Neoden4 File Creator User Guide

    ## Overview
    The Neoden4 File Creator is a tool for preparing PCB assembly files for use with Neoden4 pick-and-place machines.
    It processes PCR (Place Component Report) files into the necessary formats for both top and bottom assembly.

    ## Key Features
    • Automatic file splitting for top and bottom assembly
    • Component sorting with multiple options
    • Template file management
    • Fiducial handling
    • Manual placement identification
    • Template Override optimization
    • XY Offset correction for component positioning

    ## XY Offset Feature
    The XY Offset feature helps correct component placement when positions are off by a consistent amount. 
    This feature requires two steps:

    1. Measuring the Offset:
    • Using the N4 PNP machine's camera system
    • Aligning and marking the first component's actual position
    • Exporting the measured position data

    2. Applying the Correction:
    • Using the exported file as input
    • Calculating offset from mirror_create reference point
    • Adjusting all subsequent component positions
    • Generating a new file with corrected coordinates

    The tool will automatically:
    • Use the mirror_create position as the reference point
    • Calculate the offset from the first component
    • Apply this offset to all subsequent components
    • Generate a new file with corrected positions

    ## Template Override Feature
    • Optimizes component placement between top and bottom PCB loading
    • Preserves matched components in original positions
    • Sequentially fills unmatched positions
    • Generates component replacement tracking
    • Maintains all position and feeder data"""

        # Content for Workflow tab
        workflow_content = """# Working with Neoden4 File Creator

    ## Step 1: PCR File Preparation
    1. Export Allegro PCR file as CSV
    2. Create directory: /Neoden4Assembly/PCB_Assembly/BoardName/
    3. Save CSV file in new directory
    4. Rename fiducials to FID1, FID2, etc.

    ## Step 2: Measuring Initial Offset on N4 PNP Machine
    Before applying XY offset correction, you need to measure the initial offset:
    1. Load PCR file into N4 PNP machine
    2. Select the first component and click align
    3. Using the mouse, click the center of the component displayed in the camera view
    4. Select save to store the measured position
    5. Save and Export file to SD card
    (This exported file will be used to implement the XY OFFSET correction)

    ## Step 3: Using XY Offset Correction
    1. Click "Open PCR-file" and select your CSV file
    2. When prompted to select Template file, click Cancel
    (Template file is not needed for XY offset correction)
    3. Click the "XY OFFSET" button
    4. The system will:
    • Find the reference position from mirror_create row
    • Locate the first component after #SMD
    • Calculate and apply the offset
    • Create a new file with '_offset' suffix
    5. Review the success message for:
    • Number of modified positions
    • Applied X and Y offsets
    • Output file location

    ## Step 3: Additional Processing
    1. Click 'Split PCR' for file splitting
    2. Process template files as needed
    3. Use Generate CSV for final output

    ## Step 4: Generate Placement Files
    1. Open PCB-file and select matching board file
    2. For bottom assembly: Enter board width
    3. Select sorting options:
    • Reference Designator
    • XY Location
    • Component Value
    • Component Package
    4. Click "Generate CSV"
    5. Review generated N4_BoardName_(Top/Bot) files"""

        # Content for Troubleshooting tab
        troubleshoot_content = """# Troubleshooting Guide

    ## Initial Measurement on N4 PNP Machine
    When measuring the initial offset:
    • Ensure proper machine calibration before starting
    • Use maximum zoom for precise component centering
    • Double-check saved coordinates before exporting
    • Keep the SD card handy for file transfer

    ## Using the N4 PNP Machine
    Tips for accurate offset measurement:
    • Make sure the machine is properly calibrated before starting
    • Use the camera's maximum zoom for precise component centering
    • Verify the saved coordinates before exporting the file
    • Keep track of which component was used for measurement

    ## XY Offset Issues
    Common error messages and solutions:

    1. "Could not find 'mirror_create' row":
    • Verify the file has a mirror_create row
    • Check for correct formatting
    • Ensure no extra spaces in cell values

    2. "Could not find first component position":
    • Verify #SMD section exists
    • Check component rows after #SMD
    • Ensure X/Y values are valid numbers

    3. General Best Practices:
    • Always keep original files as backup
    • Verify offsets in generated file
    • Test with small batch first
    • Document applied offsets

    ## Other Common Issues
    • Missing template files
    • Incorrect fiducial naming
    • Board width errors
    • Component table mismatches

    ## Best Practices
    1. Use consistent value formatting
    2. Update Component Table regularly
    3. Verify fiducial detection
    4. Back up templates
    5. Double-check measurements

    ## Support Files
    Required files in pcr_files directory:
    • Component_Table.csv
    • Neoden4.csv
    • configuration.json"""