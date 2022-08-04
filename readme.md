# Image Retoucher Skill
_Alexa Skill powered by "Image Retoucher REST"_

Corresponding REST API: [`https://github.com/jnickg/image-retoucher-rest`](https://github.com/jnickg/image-retoucher-rest)

# Supported
* Alexa, Open Image Retoucher Experiment
* Edit image `X` (`X` is 0-9, one of the static resources available on the API)
* Adjust `metric` (`metric` is one of: `exposure`, `contrast`, `saturation`, `tint`)
    * `higher` or `lower` until satisfied
    * `confirm changes` when done
    * `cancel` to roll back
* Set `metric` to `val` (`metric` as above; `val` is `-100` to `100`)
* Apply `algorithm` [using image `X`] (`algorithm` is one of: `histogram equalization`, `color transfer`; if it's `color transfer` specify which image `X` to use in color transfer)

# Not yet supported
* Improved card/image visualization
* Uploading a new image from device
* Saving an iamge's changes once you're done (committing to DB or downloading)
* Login & associating images/edits with users