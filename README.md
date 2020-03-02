# notestation-to-joplin
Imports a Synology Note Station .nsx file into Joplin notes app

## Installing this Python script
- Download this repository or clone it to your project directory via  
`git clone https://github.com/KraxelHuber/notestation-to-joplin.git` or  
`git clone git@github.com:KraxelHuber/notestation-to-joplin.git` if you set up SSH keys.
- Make sure to pip install the following packages from https://pypi.org/  
  - httpx (https://pypi.org/project/httpx/)
  - pandoc (https://pypi.org/project/pandoc/)
  - joplin-api (https://pypi.org/project/joplin-api/)

## Getting your notes out of Synology's Note Station into Joplin note taking app

#### Step 1: Export your notes
- Open your Synology Note Station app in DSM.
- At the top of Note Station, click Settings.
- Under Import and Export, click Export to launch the export wizard.
- Follow the wizard instructions to export your notebooks.
- Save your .nsx file into /notestation_to_joplin/src/

#### Step 2:
- Open Joplin notes app
- Go to Tools/Options/Web Clipper
- Copy authorization token

#### Step 3:
- Open /src/nsx2joplin.py within your project folder.
- Replace `nsx_file = p.joinpath("notestation-test-books.nsx")` with your .nsx file  
`nsx_file = p.joinpath("YOUR_NSX_FILE")`
- At the end of the script, replace the line `joplin_token = ""` with your token:  
`joplin_token = "PASTE_YOUR_TOKEN_HERE"`

#### Step 4:
- Run the script (your Joplin app needs to be open).
---
This script is partly based on the great work of @Maboroshy script, which converts a .nsx file into markdown: [Note-Station-to-markdown](https://github.com/Maboroshy/Note-Station-to-markdown)  

Also, it makes use of the very good joplin-api project of @foxmask:
[joplin-api](https://github.com/foxmask/joplin-api)