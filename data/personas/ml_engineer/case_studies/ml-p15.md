<!-- project_id: ml-p15 | synthetic -->
# Keras Image Classifier for Plant Disease (Academic Collaboration)

## Context
In 2020, I partnered with an agricultural research group that was studying plant health across multiple crop varieties. The team needed a reliable, automated way to identify disease symptoms from leaf images, which would accelerate field diagnostics and reduce reliance on manual expert inspection. The project scope covered fourteen distinct plant diseases, each presenting subtle visual cues. My role as a machine learning engineer was to design and implement a deep learning solution that could handle the variability in lighting, background, and leaf orientation typical of real‑world image datasets.

## What I built
I constructed an image classification pipeline using **Keras**, leveraging a convolutional neural network architecture tailored for the problem. The workflow included:
1. **Data preprocessing** – image resizing, normalization, and augmentation (rotation, zoom, flip) to increase robustness against visual variance.
2. **Model design** – a custom **Artificial Neural Network** with multiple convolutional layers, batch normalization, and dropout to mitigate over‑fitting.
3. **Training** – the model was trained on a labeled dataset of leaf images representing the fourteen diseases, employing categorical cross‑entropy loss and the Adam optimizer.
4. **Evaluation** – validation metrics were monitored to fine‑tune hyperparameters, and a final test set was used to assess generalization.
5. **Deployment** – the trained model was exported for use in a research‑grade inference script, enabling rapid batch predictions on new images.

## Results
The final classifier achieved **92 % accuracy** across all fourteen disease categories on the held‑out test set, surpassing the research team’s baseline of manual identification. The high performance demonstrated the model’s ability to discern subtle disease patterns despite heterogeneous image conditions. The success of the project led to a co‑authored workshop paper, documenting the methodology and results, and positioned the research group to integrate the classifier into upcoming field trials. This collaboration highlighted the practical impact of deep learning in agricultural diagnostics and reinforced the value of end‑to‑end ML pipelines in scientific research.
