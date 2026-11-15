<!-- project_id: ml-p11 | synthetic -->
# Handwritten Form Digitisation (OCR) for a Clinic Network

## Context
A regional clinic network was struggling with the massive amount of paper‑based patient intake forms that doctors filled out by hand. Each day, a team of data entry clerks manually transcribed these forms into the electronic health record system, a process that was time‑consuming, error‑prone, and costly. The client needed an automated solution that could reliably read doctors' handwriting, extract the relevant fields, and feed the structured data directly into their existing workflows, thereby reducing manual effort and improving data quality.

## What I built
I designed and delivered an end‑to‑end OCR pipeline focused on handwritten medical forms. The solution combined computer‑vision preprocessing with a deep‑learning model trained specifically on the clinic’s handwriting style. Key components included:

- **Image preprocessing**: Adaptive thresholding, deskewing, and contrast enhancement to normalise the scanned documents.
- **Deep learning OCR model**: A TensorFlow‑based convolutional‑recurrent architecture (CNN + Bi‑LSTM + CTC loss) trained on a curated dataset of handwritten samples collected from the clinic’s doctors.
- **Post‑processing**: Custom rule‑based validation for medical terminology and field‑level sanity checks to correct common mis‑recognitions.
- **Integration layer**: A lightweight API that accepted scanned images, invoked the OCR model, and returned JSON‑formatted field data ready for ingestion into the clinic’s EHR system.

The model was iteratively refined through active learning, where mis‑classifications were reviewed by a small group of clinicians and fed back into the training set, continuously improving accuracy.

## Results
After deployment, the OCR system achieved a **character‑level accuracy of 94 %** on the diverse handwriting styles of the clinic’s physicians. This performance translated into a tangible operational impact:

- **Three full‑time equivalents (FTEs) of data‑entry work were eliminated**, resulting in significant cost savings.
- Manual transcription errors dropped dramatically, improving the reliability of patient records.
- Turn‑around time for form processing was reduced from hours to seconds, enabling faster clinical decision‑making.

The project demonstrated how a focused application of computer‑vision and deep‑learning techniques can modernise legacy paper workflows in healthcare, delivering both efficiency gains and higher data quality.
