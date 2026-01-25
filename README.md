# Installation

## MSE

1. Install it via following the installation in https://github.com/MagicSetEditorPacks/M15-Magic-Pack/?tab=readme-ov-file#installation (tested with version 2.5.6)
2. Open MSE and click open set. Choose the set file in MSE/sets/Chaos Crawl The Fould Realms.mse-set in this repo
3. Enjoy the set within MSE

Note MSE has also a github repository: https://github.com/MagicSetEditorPacks/M15-Magic-Pack

### How to use the command tool of MSE

Use the magicseteditor.com file of the downloaded folder.


## Cockatrice

1. Install Cockatrice via https://cockatrice.github.io/ (tested with version 2.10.2)
2. Copy and Replace Cockatrice/data folder with the Cockatrice/data folder in this repo 
3. Start Cockatrice and find the set in the card database

## Forge

# Set Imports

## MSE -> Cockatrice

For the export to work flawlessly an adapted export template can be found in `MSE/data/magic-cockatrice-v2.mse-export-template\export-template`. The default export of the cockatrice exporter exports special characters to the name tag of cards in the xml set file which leads to issues linking to the correct image which can't contain those special characters. The updated export-template removes all special characters which can't be part of an image filename so the cards are linked correctly to their images. 

# Note step 1 can be done by the script
1. Export from MSE
    - Go to File->Export-> HTML...
    - Use settings as shown in the screenshot: ![cockatrice_export](docs/images/MSE_Cockatrice_export.png)
2. Prepare/Reformat exported .xml file
    - Use script `TBD` to reformat the exported xml. It will clean every special characters within the name tag to fix the link between xml entry and card image
3. Import to Cockatrice
    - Copy the images into your installation of Cockatrice `Cockatrice/data/pics/CUSTOM/`
    - Copy the cleaned xml file into `Cockatrice/data/customsets`
4. Start Cockatrice and find the set in the card database

## MSE -> Forge

