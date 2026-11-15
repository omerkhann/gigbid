<!-- project_id: ml-p03 | synthetic -->
# Defect Detection on a Bottling Line

## Context
In 2024, a manufacturing client sought to improve quality control on its bottling line. The existing visual inspection system missed a significant number of cracked caps, leading to product returns and brand reputation risk. The client needed a reliable, real‑time solution that could run on edge hardware without disrupting the high‑throughput production environment. The goal was to achieve high recall for defect detection while maintaining the line speed of 30 frames per second (fps).

## What I built
I designed an end‑to‑end computer‑vision pipeline that leveraged deep learning for defect classification and classic image‑processing techniques for pre‑ and post‑processing. The workflow consisted of:

1. **Data acquisition and labeling** – Captured thousands of high‑resolution images of bottle caps under varying lighting conditions and annotated cracked versus intact caps.
2. **Pre‑processing** – Applied OpenCV‑based normalization, contrast enhancement, and region‑of‑interest cropping to focus the model on the cap area and reduce background noise.
3. **Model architecture** – Trained a lightweight convolutional neural network in PyTorch, fine‑tuned from a pretrained backbone to balance accuracy and inference speed on edge GPUs.
4. **Inference engine** – Integrated the model into a real‑time inference loop using TorchScript, optimized for the client’s NVIDIA Jetson edge device. The pipeline processes each frame at 30 fps, applying post‑processing filters to suppress false positives.
5. **Deployment and monitoring** – Deployed the solution on the production line, establishing telemetry dashboards to track recall, precision, and latency.

## Results
The deployed system achieved a **recall of 96 %** for detecting cracked caps, dramatically reducing missed defects compared with the legacy setup. It maintained the required **30 fps processing rate** on the edge GPU, ensuring no bottleneck in the bottling line. The client reported a measurable decline in product returns and an improvement in overall quality metrics, validating the impact of the solution on both operational efficiency and brand trust.
