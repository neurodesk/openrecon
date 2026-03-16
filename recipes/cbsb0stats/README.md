# Open Recon B0map Container
**NOTE: This container has not been tested on a brain yet**

## Outline:
+ This container is designed to work with a gradient field echo sequence with 2 magntiude images of echo times TE1 and TE2 and a phase difference image. 
  
+ The Container constructs a B0map image from these sequences via a Brain Mask of the subject using [BET2](https://poc.vl-e.nl/distribution/manual/fsl-3.2/bet2/) and the T1 image data.

+ Additionally the Mean and standard deviation are calculated and displayed in the image comments as well as in the logs.

+ This is an image-to-image container

## Config Parameters
- **Config (choice):** There is no choice here the only option is the B0map script
- **Number of Dilations (int):** the number of dilations performed on the Brain Mask. Dilations are performed using
    scipy.ndimage.binary_dilation(BrainMask,iterations={Number of Dilations}) 
    NOTE: Dilations happen before Erosions
    - **Min:** 0 
    - **Max:** 100
    - **Default:** 2

- **Number of Erosions (int):** the number of erosions performed on the Brain Mask. Erosions are performed using
    scipy.ndimage.binary_erosion(BrainMask,iterations={Number of Erosions}) 
    NOTE: Dilations happen before Erosions
    - **Min:** 0 
    - **Max:** 100
    - **Default:** 3

- **Fractional Intensity (double):** The fractional threshold of the [BET2](https://poc.vl-e.nl/distribution/manual/fsl-3.2/bet2/) brain mask, smaller values give larger brain outline estimates
    - **Min:** 0.0
    - **Max:** 1.0
    - **Default:** 0.4

- **Send Originals (boolean):** When Send Originals is True the 2 magnitude and phase difference images are sent back unmodified.
  - **Default:** True

- **TE1/TE2 (str):** These two are optional and serve as a manual backup in case the echo times of the Mag 1 and Mag 2 images cannot be found. TE1 and TE2 are in units of milliseconds and they must be entered in as "3.06" not "3,06". It is recommended to input these values if they are easily accessible in the Program Card.
    - **TE1 Default:** "3.06"
    - **TE2 Default:** "4.08"
    - **Delta TE Default:** "1.02"

**NOTE: These are entered as string variables if they do not follow a float convention they will be disregarded.**

- **Verbose Logging (boolean):** Enables extra logging of data arrays and the B0map process steps.
    - **Default:** False
