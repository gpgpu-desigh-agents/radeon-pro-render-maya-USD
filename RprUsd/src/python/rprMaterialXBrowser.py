#
# Copyright 2023 Advanced Micro Devices, Inc
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#    http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import maya.cmds as cmds
import maya.mel as mel
import os
import json
import math
from funcagents import partial
from sys import platform
import zipfile
import threading
from client import MatlibClient
import webServerUrlHelper

import ufe

# Show the material browser window.
# -----------------------------------------------------------------------------
def show() :
    RPRMaterialBrowser().show()

# A material browser window for Radeon Pro Render materials.
# -----------------------------------------------------------------------------
class RPRMaterialBrowser(object) :

    # Constructor.
    # -----------------------------------------------------------------------------
    def __init__(self, *args) :

        # Character lengths used to calculate label widths.
        self.charLengths = [3, 3, 4, 7, 6, 9, 9, 3, 3, 3, 5, 8, 3, 4, 3, 4, 6, 6, 6, 6, 6, 6, 6,
                            6, 6, 6, 3, 3, 8, 8, 8, 5, 11, 7, 7, 7, 8, 6, 6, 8, 8, 3, 4, 6, 5, 10,
                            8, 9, 6, 9, 7, 6, 5, 8, 7, 11, 6, 5, 6, 3, 4, 3, 8, 5, 3, 6, 7, 5, 7,
                            6, 4, 7, 7, 3, 3, 6, 3, 9, 7, 7, 7, 7, 4, 5, 4, 7, 5, 9, 5, 5, 5, 3,
                            3, 3, 8, 6, 6, 0, 3, 6, 4, 9, 4, 4, 4, 13, 6, 3, 10, 0, 6, 0, 0, 3, 3,
                            4, 4, 4, 6, 11, 4, 9, 5, 3, 10, 0, 5, 5, 3, 3, 6, 6, 7, 6, 3, 5, 5,
                            10, 4, 6, 8, 0, 10, 5, 4, 8, 4, 4, 3, 7, 5, 3, 2, 4, 5, 6, 10, 10, 10,
                            5, 7, 7, 7, 7, 7, 7, 9, 7, 6, 6, 6, 6, 3, 3, 3, 3, 8, 8, 9, 9, 9, 9,
                            9, 8, 9, 8, 8, 8, 8, 5, 6, 6, 6, 6, 6, 6, 6, 6, 9, 5, 6, 6, 6, 6, 3,
                            3, 3, 3, 7, 7, 7, 7, 7, 7, 7, 8, 7, 7, 7, 7, 7, 5, 7, 5]

        # Panel background color.
        self.backgroundColor = [0.16862745098039217, 0.16862745098039217, 0.16862745098039217]

        self.uiMayaScaleCoeff = cmds.mayaDpiSetting(q=True, rsv=True)

        # Set the default material icon size.
        self.setMaterialIconSize(self.getDefaultMaterialIconSize())

    # Show the material browser.
    # -----------------------------------------------------------------------------
    def show(self) :

        #load all material at one time. It's possible to rework to load in chunks if needs
        maxElementCount = 10000

        self.matlibClient = MatlibClient(webServerUrlHelper.g_WebMatXServerUrl)
        self.categoryListData = self.matlibClient.categories.get_list(maxElementCount, 0)
        self.pathRootThumbnail = os.environ["USERPROFILE"] + "/Documents/Maya/RprUsd/WebMatlibCache"
        os.makedirs(self.pathRootThumbnail, exist_ok=True)

        if len(self.categoryListData) <= 0 :
            print("ML Log: ERROR: We couldn't load categories from the Web")	
            return

        self.categoryDict = dict()

        for category in self.categoryListData :
            self.categoryDict[category["id"]] = category

        self.tags = self.matlibClient.tags.get_list(maxElementCount, 0)

        self.tagDict = dict()
        for tag in self.tags :
            self.tagDict[tag["id"]] = tag["title"]

        self.materialListData = self.matlibClient.materials.get_list(maxElementCount, 0)
        self.materialDict = dict()
      
        self.materialByCategory = dict()

        for material in self.materialListData :
            self.materialDict[material["id"]] = material
            categoryId = material["category"]

            if categoryId not in self.materialByCategory :
                self.materialByCategory[categoryId] = list()
            self.materialByCategory[categoryId].append(material)
              	     		
        self.createLayout()

    # Create the browser layout.
    # -----------------------------------------------------------------------------
    def createLayout(self) :

        # Delete any existing window.
        if (cmds.window("RPRMaterialBrowserWindow", exists = True)) :
            cmds.deleteUI("RPRMaterialBrowserWindow")

        # Create a new window.
        self.window = cmds.window("RPRMaterialBrowserWindow",
                                  widthHeight=(1200, 700),
                                  title="Radeon ProRender MaterialX Browser")

        # Place UI sections in a horizontal 3 pane layout.
        paneLayout = cmds.paneLayout(configuration='vertical3', staticWidthPane=3,
                                     separatorMovedCommand=self.updateMaterialsLayout)

        cmds.paneLayout(paneLayout, edit=True, paneSize=(1, 22, 100))
        cmds.paneLayout(paneLayout, edit=True, paneSize=(2, 48, 100))
        cmds.paneLayout(paneLayout, edit=True, paneSize=(3, 30, 100))

        # Create UI sections.
        self.createCategoriesLayout()
        self.createMaterialsLayout()
        self.createSelectedLayout()

        cmds.setParent('..')

        # Select the first material of the first category.
        self.selectCategory(0)
        self.selectMaterial(0)

        # Show the material browser window.
        cmds.showWindow(self.window)

        # Initialize the layout.
        self.initializeLayout();

    # Create the material categories layout.
    # -----------------------------------------------------------------------------
    def createCategoriesLayout(self) :

        # Create tab, form and scroll layouts.
        tabLayout = cmds.tabLayout(innerMarginWidth=5, innerMarginHeight=15, borderStyle="full")
        formLayout = cmds.formLayout(numberOfDivisions=100)
        scrollLayout = cmds.scrollLayout(backgroundColor=self.backgroundColor,
                                         horizontalScrollBarThickness=0,
                                         verticalScrollBarThickness=16,
                                         childResizable=True)

        # Lay out categories vertically.
        catergories = cmds.columnLayout()

        # Add layouts with index based names for easy lookup.
        index = 0

        for category in self.categoryListData :
            cmds.iconTextButton("RPRCategory" + str(index), style='iconAndTextHorizontal',
                                image='material_browser/folder_closed.png',
                                label=category["title"], height=20,
                                command=partial(self.selectCategory, index))
            index += 1

        # Assign the form to the tab.
        cmds.tabLayout(tabLayout, edit=True, tabLabel=((formLayout, 'Categories')))

        # Lay out components within the form.
        cmds.formLayout(formLayout, edit=True,
                        attachForm=[(scrollLayout, 'top', 5), (scrollLayout, 'left', 5),
                                    (scrollLayout, 'bottom', 5), (scrollLayout, 'right', 5)])

        cmds.setParent('..')
        cmds.setParent('..')
        cmds.setParent('..')
        cmds.setParent('..')

    def getMaterialFileName(self, material) :
        render_id = material["renders_order"][0]
        return render_id + ".png"

    def getMaterialFullPath(self, fileName) :
        return os.path.join(self.pathRootThumbnail, fileName)

    def onSortModeChanged(self, modeName) :
        mode = cmds.optionMenu(self.sortDropdown, q=True, select=True)
        self.sortMaterials(mode)
        self.populateMaterialsInternal()

    # 1 - No Sort, 2 - Ascending, 3 - Descending
    def sortMaterials(self, mode) :
        if mode == 1 :
            self.materials = self.nonSortedMaterials.copy()
        else :
            self.materials = sorted(self.nonSortedMaterials, key=lambda material: material["title"], reverse = (mode == 3) )
    # Create the materials layout.
    # -----------------------------------------------------------------------------
    def createMaterialsLayout(self) :
	
        # Create the tab and form layouts.
        self.materialsTab = cmds.tabLayout(borderStyle="full")
        self.materialsForm = cmds.formLayout(numberOfDivisions=100)

        # Add the icon size slider.
        topRow = cmds.rowLayout("RPRWMLTopRow", numberOfColumns=6)

        iconSizeRow = cmds.rowLayout("RPRIconSize", numberOfColumns=2, columnWidth=(1, 22))
        cmds.image(image='material_browser/thumbnails.png')
        self.iconSizeSlider = cmds.intSlider(width=120, step=1, minValue=1, maxValue=4,
                                             value=self.getDefaultMaterialIconSize(),
                                             dragCommand=self.updateMaterialIconSize)
        cmds.setParent('..')

        cmds.separator(width=10,style="none")

        # Add the search field.
        cmds.text(label="Sort Mode: ")
        self.sortDropdown = cmds.optionMenu(cc=self.onSortModeChanged)
        cmds.menuItem(p=self.sortDropdown, l="No Sort")
        cmds.menuItem(p=self.sortDropdown, l="Sort Ascending")
        cmds.menuItem(p=self.sortDropdown, l="Sort Descending")

        cmds.image(image='material_browser/search.png')
        self.searchField = cmds.textField(placeholderText="Search...", width=150, height=22,
                                          textChangedCommand=self.searchMaterials)

        cmds.setParent('..') # toRow

        # Add help text.
        helpText = cmds.text(label="Select material, choose package you wish and click the Download button.")

        # Add the background canvas.
        bg = cmds.canvas(rgbValue=self.backgroundColor)

        # Add the scroll layout that will contain the material icons.
        self.materialsContainer = cmds.scrollLayout(backgroundColor=self.backgroundColor, childResizable=True,
                                                    resizeCommand=self.updateMaterialsLayout)
        cmds.setParent('..')

        # Assign the form to the tab.
        cmds.tabLayout(self.materialsTab, edit=True, tabLabel=((self.materialsForm, 'Materials')))

        # Lay out components within the form.
        cmds.formLayout(self.materialsForm, edit=True,
                        attachForm=[(topRow, 'top', 5), (topRow, 'left', 5),
                                    (self.materialsContainer, 'left', 5), 
                                    (self.materialsContainer, 'bottom', 20),
                                    (self.materialsContainer, 'right', 5),
                                    (helpText, 'left', 10), (helpText, 'bottom', 5),                                   
                                    (bg, 'left', 5), (bg, 'bottom', 20), (bg, 'right', 5)],
                        attachControl=[(self.materialsContainer, 'top', 10, topRow),
                                       (bg, 'top', 5, topRow)])

        cmds.setParent('..')
        cmds.setParent('..')

        # Initialize the currently selected category index.
        self.selectedCategoryIndex = 0


    # Create the selected material layout.
    # -----------------------------------------------------------------------------
    def createSelectedLayout(self) :

        # Create a pane layout to contain material info and preview.
        paneLayout = cmds.paneLayout("RPRSelectedPane", configuration='horizontal2', staticHeightPane=2,
                                     separatorMovedCommand=self.updatePreviewLayout)

        self.createInfoLayout()
        self.createPreviewLayout()


    # Perform initial layout tasks.
    # -----------------------------------------------------------------------------
    def initializeLayout(self) :

        # Configure the selected pane.
        cmds.paneLayout("RPRSelectedPane", e=True, paneSize=(1, 100, 50))
        cmds.paneLayout("RPRSelectedPane", e=True, paneSize=(2, 100, 50))

        # Perform an initial preview layout update.
        self.updatePreviewLayout()


    # Create the info layout.
    # -----------------------------------------------------------------------------
    def createInfoLayout(self) :

        # Create tab and form layouts.
        tabLayout = cmds.tabLayout(innerMarginWidth=8, innerMarginHeight=8, borderStyle="full")
        formLayout = cmds.formLayout(numberOfDivisions=100)       

        # Add the RPR logo.
        logoBackground = cmds.canvas("RPRLogoBackground", rgbValue=[0, 0, 0])
        logo = cmds.iconTextStaticLabel("RPRLogo", style='iconOnly',
                                        image="RadeonProRenderLogo.png", width=1, height=1)

        scrollLayout = cmds.scrollLayout()  
        # Add material info text.
        columnLayout = cmds.columnLayout(rowSpacing=5)

        cmds.text(label="Category:", font="boldLabelFont")
        cmds.text("RPRCategoryText", recomputeSize=False)

        cmds.text(label="Name:", font="boldLabelFont")
        cmds.text("RPRNameText", recomputeSize=False)

        cmds.text(label="License:", font="boldLabelFont")
        cmds.text("RPRMaterialLicense", recomputeSize=False)

        self.downloadPackageDropdown = cmds.optionMenu()

        downloadButton = cmds.button(label="Download", w=100, h=30, command=self.downloadMaterial)
        assignMatXLiveModeButton = cmds.button(label="Assign Material", w=100, h=30, command=self.assignMatXLiveMode)

        cmds.setParent('..') #columnLayout

        cmds.setParent('..') #scrollLayout

        cmds.setParent('..') #formLayout

        cmds.setParent('..') #tabLayout

        # Assign the form to the tab.
        cmds.tabLayout(tabLayout, edit=True, tabLabel=((formLayout, 'Info')))

        cmds.formLayout(formLayout, edit=True,
                        attachControl=[(scrollLayout, 'top', 10, logo)],
                        attachForm=[(logo, 'left', 8), (logo, 'right', 8), (logo, 'top', 8),
                                    (logoBackground, 'left', 8), (logoBackground, 'right', 8),
                                    (logoBackground, 'top', 8), 
                                    (scrollLayout, 'left', 5), (scrollLayout, 'right', 5), (scrollLayout, 'bottom', 5)])


    # Create the preview layout.
    # -----------------------------------------------------------------------------
    def createPreviewLayout(self) :

        # Create tab layout.
        tabLayout = cmds.tabLayout(borderStyle="full")

        # Add horizontal and vertical flow layouts and
        # spacers to center the image in the preview area.
        formLayout = cmds.formLayout("RPRPreviewArea")

        cmds.iconTextStaticLabel("RPRPreviewImage", style='iconOnly', width=1, height=1)

        cmds.setParent('..')
        cmds.setParent('..')
        cmds.setParent('..')

        # Assign the top flow layout to the tab.
        cmds.tabLayout(tabLayout, edit=True, tabLabel=((formLayout, 'Preview')))


    # Select a material category by index.
    # -----------------------------------------------------------------------------
    def selectCategory(self, index) :
	
        # Populate the materials view from the selected category.
        self.materials = self.materialByCategory[self.categoryListData[index]["id"]]
        self.populateMaterials()

        # Update the folder open / closed state on the category list.
        cmds.iconTextButton("RPRCategory" + str(self.selectedCategoryIndex),
                            edit=True, image='material_browser/folder_closed.png')

        cmds.iconTextButton("RPRCategory" + str(index),
                            edit=True, image='material_browser/folder_open.png')

        self.selectedCategoryIndex = index

        # Clear the search field.
        cmds.textField(self.searchField, edit=True, text="")

    def downloadPackageCallback(self, size, length) :
        
        percent = int(100 * size / length)
        cmds.progressWindow( edit=True, progress=percent, status=('Downloading: ' + str(percent) + '%' ) )

        return True

    def downloadMaterial(self, *args) :
        menuItems = cmds.optionMenu(self.downloadPackageDropdown, q=True, itemListLong=True) # itemListLong returns the children
        index = cmds.optionMenu(self.downloadPackageDropdown, q=True, select=True) - 1

        package = self.packageDataList[index]
        packageId = package["id"]
        
        optionVarNameRecentDirectory = "RprUsd_DownloadPackageRecentDirectory"
        previousDirectoryUsed = ""
        if cmds.optionVar(exists=optionVarNameRecentDirectory) :
            previousDirectoryUsed = cmds.optionVar(query=optionVarNameRecentDirectory)
        
        path = cmds.fileDialog2(cap="Select A Directory", startingDirectory=previousDirectoryUsed, fm=3)
        cmds.progressWindow( title='Downloading Package',progress=0,status='downloading: 0%',isInterruptable=False)
        if path is not None :
            print("ML Log: start downloading packageId=" + packageId)
            self.matlibClient.packages.download(packageId, self.downloadPackageCallback, path[0], package["file"])
            cmds.optionVar(sv=(optionVarNameRecentDirectory, path[0]))

            zipFileName = os.path.join(path[0], package["file"])
        
            fullPathToExtract = os.path.join(path[0], os.path.splitext(package["file"])[0])
            os.makedirs(fullPathToExtract, exist_ok=True)

            #unzip
            with zipfile.ZipFile(zipFileName, 'r') as zip_ref:
                zip_ref.extractall(fullPathToExtract)
            # remnove zip-archive
            os.remove(zipFileName)
                                                                                                               
        cmds.progressWindow(endProgress=1)

    def assignMatXLiveMode(self, *args) :
        gsel = ufe.GlobalSelection.get()
        pathList = list(gsel)    
        while len(pathList) > 0 :
            selected_path = str(pathList.pop().path())
            selected_path = selected_path[selected_path.find("/"):len(selected_path)]
            cmds.rprUsdBindMtlx(lm=1, pp=selected_path, id=self.selectedMaterial["id"])

    def updateSelectedMaterialPanel(self, fileName, categoryName, materialName, materialType, license) :

        def sortAccordingPackageSize(package) :
            numberDirtyString = package["size"]
            return float(''.join(c for c in numberDirtyString if (c.isdigit() or c =='.')))

        imageFileName = self.getMaterialFullPath(fileName)
		
        cmds.iconTextStaticLabel("RPRPreviewImage", edit=True, image=imageFileName)
        cmds.text("RPRCategoryText", edit=True, label=categoryName)
        cmds.text("RPRNameText", edit=True, label=materialName)
        cmds.text("RPRMaterialLicense", edit=True, label=license)
            
        params = dict()
        params["material"] = self.selectedMaterial["id"]
        self.packageDataList = self.matlibClient.packages.get_list(limit=100, offset=0, params = params)
          
        self.packageDataList.sort(key=sortAccordingPackageSize)

        menuItems = cmds.optionMenu(self.downloadPackageDropdown, q=True, itemListLong=True) # itemListLong returns the children
        if menuItems:
            cmds.deleteUI(menuItems)

        index = 0
        for package in self.packageDataList:
            menuItemName = "Package: " + package["label"] + " ( " + package["size"] + " )"
            cmd = partial(self.downloadMaterial, package)

            cmds.menuItem(p=self.downloadPackageDropdown, l=menuItemName, data=index)

            index += 1

    def selectMaterial(self, materialIndex) :

        self.selectedMaterial = self.materials[materialIndex]
        material = self.selectedMaterial
        fileName = self.getMaterialFileName(self.selectedMaterial)

        self.updateSelectedMaterialPanel(fileName, self.categoryDict[material["category"]]["title"], material["title"], material["material_type"], material["license"])

        self.updatePreviewLayout()

    # Update the height of the materials flow layout
    # based on the width of its container and the
    # number of children. This is required so
    # a scrollable flow layout works properly.
    # -----------------------------------------------------------------------------
    def updateMaterialsLayout(self) :
        
        # Determine the width of the material view
        # and the total number of materials to display.
        width = cmds.scrollLayout(self.materialsContainer, query=True, width=True)      

        count = cmds.flowLayout("RPRMaterialsFlow", query=True, numberOfChildren=True)

        if (count <= 0) :
            return

        # Calculate the number of materials that can fit on
        # a row and the total required height of the container.
        perRow = max(1, math.floor((width) / (self.cellWidth * self.uiMayaScaleCoeff)))
        height = math.ceil(count / perRow) * self.cellHeight

        cmds.flowLayout("RPRMaterialsFlow", edit=True, height=height)

        # Adjust the form to be narrower than the tab that
        # contains it. This is required so the form doesn't
        # prevent the tab layout shrinking.
        materialsWidth = cmds.tabLayout(self.materialsTab, query=True, width=True)
        newMaterialsWidth = max(1, materialsWidth - 10 * self.uiMayaScaleCoeff)

        # Update the preview layout.
        self.updatePreviewLayout()


    # Update the size and position of the preview image.
    # This is required because the script-able Maya UI
    # doesn't provide enough control over layout.
    # -----------------------------------------------------------------------------
    def updatePreviewLayout(self) :

        # Determine the size of the preview area.
        width = cmds.formLayout("RPRPreviewArea", query=True, width=True)
        height = cmds.formLayout("RPRPreviewArea", query=True, height=True)

        # Choose the smallest dimension and shrink
        # slightly so the enclosing layouts can shrink.
        size = min(width, height) - 10

        # Calculate the horizontal and vertical
        # offsets required to center the preview image.
        hOffset = max(0, (width - size) / 2.0 / self.uiMayaScaleCoeff)
        vOffset = max(0, (height - size) / 2.0 / self.uiMayaScaleCoeff)

        # Clamp the size to a minimum of 64.
        size = max(64, size) / self.uiMayaScaleCoeff;

        # Update the layout and image size.
        cmds.iconTextStaticLabel("RPRPreviewImage", edit=True, width=size, height=size)

        cmds.formLayout("RPRPreviewArea", edit=True,
                        attachForm=[("RPRPreviewImage", 'left', hOffset), ("RPRPreviewImage", 'top', vOffset)])

        # Update the RPR logo size.
        logoWidth = cmds.iconTextStaticLabel("RPRLogo", query=True, width=True)
        logoHeight = max(min(logoWidth * 0.16, 60), 1)
        cmds.iconTextStaticLabel("RPRLogo", edit=True, height=logoHeight)
        cmds.canvas("RPRLogoBackground", edit=True, height=logoHeight)


    # Update the material icon size from the slider.
    # -----------------------------------------------------------------------------
    def updateMaterialIconSize(self, *args) :

        # Calculate the new icon size and repopulate the view.
        value = cmds.intSlider(self.iconSizeSlider, query=True, value=True)
        self.setMaterialIconSize(value)
        self.populateMaterials()

        # Save the size setting to user preferences.
        cmds.optionVar(intValue=['RPRIconSize', value])


    # Set the size of the material icons.
    # -----------------------------------------------------------------------------
    def setMaterialIconSize(self, value) :

        # Set the size to a power of two.
        size = pow(2, value + 4)
        self.iconSize = size

        # Use horizontal cells for small icons
        # and vertical cells for large icons.
        if (size < 64) :
            self.cellWidth = size + 200
            self.cellHeight = size + 10
        else :
            self.cellWidth = size + 10
            self.cellHeight = size + 30


    # Get the default icon size value.
    # -----------------------------------------------------------------------------
    def getDefaultMaterialIconSize(self) :

        # Query user preferences.
        if (cmds.optionVar(exists="RPRIconSize")) :
            return cmds.optionVar(query="RPRIconSize")

        # Use a default value if no preference found.
        return 3


    # Search materials for the specified string.
    # -----------------------------------------------------------------------------
    def searchMaterials(self, *args) :

        # Convert the search string to lower
        # case so the search is not case sensitive.
        searchString = cmds.textField(self.searchField, query=True, text=True).lower()
		
        # Check that the string is long enough
        # to search and not whitespace.
        if (len(searchString) < 2 or searchString.isspace()) :
            return

        # Set current materials to the search result.
        self.materials = []

        for material in self.materialListData:
            if (searchString in material["title"].lower()) :
                self.materials.append(material)
            else :
                for tagId in material["tags"] :
                    if (searchString == self.tagDict[tagId].lower()) :
                        self.materials.append(material)
                        break;

        # Repopulate the material view.
        self.populateMaterials()

    # Populate the materials view with a list of materials.
    # -----------------------------------------------------------------------------

    def populateMaterials(self) :
        self.nonSortedMaterials = self.materials.copy()
        self.sortMaterials(cmds.optionMenu(self.sortDropdown, q=True, select=True))
        self.populateMaterialsInternal()

    def threadProcDownloadThumbnail(self, render_id, fileName) :
        self.matlibClient.renders.download_thumbnail(render_id, None, self.pathRootThumbnail, fileName)

    def downloadThumbnails(self) :
        threadCount = 0
        progressBarShown = False

        threads = []        
        for material in self.materials :
            fileName = self.getMaterialFileName(material)
            imageFileName = self.getMaterialFullPath(fileName)

            # Checks if end condition has been reached
            render_id = material["renders_order"][0]

            if (not os.path.isfile(imageFileName)) :
                if (not progressBarShown) : 
                    cmds.progressWindow( title='Opening materials ', progress=0, status='opening: 0%', isInterruptable=False )
                    progressBarShown = True 

                thread = threading.Thread(target=self.threadProcDownloadThumbnail, args=(render_id, fileName))
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()
            threadCount += 1
            percent = int(100 * threadCount / len(threads))
            cmds.progressWindow( edit=True, progress=percent, status=('opening: ' + str(percent) + '%' ) )

        if (progressBarShown) : 
            cmds.progressWindow( endProgress=1 )
      

    def populateMaterialsInternal(self) :
        # Remove any existing materials.
        if (cmds.layout("RPRMaterialsFlow", exists=True)) :
            cmds.deleteUI("RPRMaterialsFlow", layout=True)

        # Ensure that the material container is the current parent.
        cmds.setParent(self.materialsContainer)

        # Create the new flow layout.
        cmds.flowLayout("RPRMaterialsFlow", columnSpacing=0, wrap=True)

        self.downloadThumbnails()

        materialIndex = 0

        # Add materials for the selected category.
        for material in self.materials :
            fileName = self.getMaterialFileName(material)
            cmd = partial(self.selectMaterial, materialIndex)
            imageFileName = self.getMaterialFullPath(fileName)

            materialName = material["title"]

            # Horizontal layout for small icons.
            if (self.iconSize < 64) :
                iconWidth = self.iconSize + 5
                cmds.rowLayout(width=self.cellWidth, height=self.cellHeight, numberOfColumns=2,
                               columnWidth2=(self.iconSize, self.cellWidth - iconWidth - 5))

                cmds.iconTextButton(style='iconOnly', image=imageFileName, width=self.iconSize,
                                    height=self.iconSize, command=cmd)

                cmds.iconTextButton(style='textOnly', height=self.iconSize,
                                    label=self.getTruncatedText(materialName, self.cellWidth - iconWidth - 5),
                                    align="left", command=cmd)

            # Vertical layout for large icons.
            else :
                cmds.columnLayout(width=self.cellWidth, height=self.cellHeight)
                cmds.iconTextButton(style='iconOnly', image=imageFileName, width=self.iconSize,
                                    height=self.iconSize, command=cmd)
                cmds.text(label=self.getTruncatedText(materialName, self.iconSize),
                          align="center", width=self.iconSize)

            cmds.setParent('..')
            materialIndex += 1

        # Perform an initial layout update.
        self.updateMaterialsLayout()


    # Import the currently selected material into Maya.
    # -----------------------------------------------------------------------------
    #def importSelectedMaterial(self, *args) :
    #    self.importMaterial(self.selectedMaterial)



    # Return the width of a text UI element given it's label string.
    # -----------------------------------------------------------------------------
    def getTextWidth(self, text) :

        # Iterate over the string characters adding character widths.
        width = 0
        charCount = len(self.charLengths)

        for c in text :
            i = ord(c) - 32

            if (i < 0 or i >= charCount) :
                continue

            width += self.charLengths[i]

        return width


    # Return a string truncated to fit in the required width if necessary.
    # -----------------------------------------------------------------------------
    def getTruncatedText(self, text, requiredWidth) :

        # Return the string immediately if it fits within the required width.
        if (self.getTextWidth(text) < requiredWidth) :
            return text

        # Reserve enough space for the ellipsis (...).
        requiredWidth -= (self.getTextWidth(".") * 3)

        # Iterate over the string characters.
        width = 0
        charCount = len(self.charLengths)
        truncated = ""

        for c in text :

            # Get the index of the character in the char lengths array.
            i = ord(c) - 32
            if (i < 0 or i >= charCount) :
                continue

            width += self.charLengths[i]

            # Add characters until the required width is reached.
            if (width < requiredWidth) :
                truncated += c
            else :
                break

        # Add the ellipsis.
        if (len(truncated) < len(text)) :
            truncated += "..."

        return truncated
