# !/bin/bash

# First get the set file as imput
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path-to-mse-set-file>"
    exit 1
fi
# secondly get an output path for the xml file
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <path-to-mse-set-file> <output-xml-file>"
    exit 1
fi
# thirdly output path for all images
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <path-to-mse-set-file> <output-xml-file> <output-images-folder>"
    exit 1
fi  
# Export xml file
echo "Exporting cockatrice xml set file: $2 ..."
./magicseteditor.com --export magic-cockatrice-v2 chaosbrawl.mse-set chaosbrawl.xml
# export images
echo "Exporting xml file completed!"
echo "Exporting images to $3 ..."
../magicseteditor.com --export-images $3
echo "Exporting images completed!"


