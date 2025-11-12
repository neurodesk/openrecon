# CBSB0STATS Recipe
**WARNING: This recipe has not yet been tested on an MRI Machine**

This recipe creates b0 map from a gre field map (2 magnitude images with TE1 and TE2, and a 1 phase difference image.) and calculates the mean and std of the created b0 map.

cbsb0stats assumes your first scan is a gre field map, and thus will attempt to create a b0-map from the first 3 images, (assume to be 2 magnitude images and 1 phase difference image). After this it will ignore all further images and pass them through without alteration.

## UI Parameters
- (choice) Config:
  - a choice selection to select cbsb0stats
- (bool) sendoriginal:
  - Also sends unprocessed first 3 images, (may muck up image series index and instance numbers counters)
  - When collecting the first 3 images to create the b0map it also processes the 2 magnitude and 1 phase difference image, labelling them in **ImageProcessingHistory** with "PYTHON" and "B0MAP" as well as in **SequenceDescriptionAdditional** with "OpenRecon_cbsb0stats".

- (double) Echo Time 1 and Echo Time 2:
   - Optional to manually enter TE1 and TE2, however cbsb0stats will first attempt to collect Echo Time 1 and 2 from the dicoms themselves then resort to this parameter.
