# ROSIE SLM

ROSIE is a small, locally runnable language-model project built as a hands-on exploration of how a compact language model can be trained, tested, and evolved toward robotics-oriented applications.

The goal is not to compete with large foundation models. ROSIE focuses on understanding the complete pipeline:

**data -> preprocessing -> model -> training -> evaluation -> inference -> robotics-oriented use cases**

## 1. Why ROSIE?

ROSIE started as an exploration of building and working with a Small Language Model (SLM) rather than treating an LLM as a black box.

This repository documents:

- the scripts used to prepare and process data
- model and training experiments
- inference and testing scripts
- actual outputs and observations
- experiments that identify strengths and weaknesses
- the evolution of ROSIE toward robotics-related interaction and reasoning

The repository is both a technical project record and a learning reference.

## 2. Project Structure

```text
Rosie-SLM/
|
+-- README.txt
+-- scripts/
|   +-- data/              # Data preparation / preprocessing
|   +-- training/          # Model training
|   +-- inference/         # Prediction / inference
|   +-- evaluation/        # Evaluation and testing
|   +-- utilities/         # Helper scripts
|+-- outputs/			   # Benchmark results
|+-- images/
|
```

## 3. Development Philosophy

ROSIE is developed experimentally and incrementally.

Each experiment should answer a specific question:

1. Can the model learn the intended task?
2. What happens when the training data changes?
3. Does another training epoch improve the results?
4. Which inputs produce reliable outputs?
5. Where does the model fail?
6. Can the same approach be extended toward robotics?

Results should be recorded, including failures, rather than showing only successful examples.

## 4. Scripts

The `scripts/` directory contains the implementation used during experiments.

### Data
Scripts for loading datasets, cleaning data, transforming labels, creating splits, and preparing custom examples.

### Training
Scripts for initializing the model, loading data, training, saving checkpoints, resuming training, and recording losses.

### Inference
Scripts for loading the trained model, accepting a sentence or command, running inference, and formatting Top-K results.

### Evaluation
Scripts for repeatable test cases, expected-vs-predicted comparisons, metrics, and result generation.

## 5. Experiments

Each meaningful experiment should have a short record:

```text
Experiment:
Date:
Goal:
Dataset:
Model:
Training configuration:
Epoch:
Result:
What changed:
Observation:
Next step:
```

This makes the evolution of ROSIE understandable instead of showing only the final model.

## 6. Testing

ROSIE should be tested with:

- normal examples
- difficult examples
- edge cases
- unseen inputs
- repeated tests after model changes

For each test, capture:

```text
Input
Expected behavior
Model output
Score / confidence
Pass / Fail
Observation
```

Representative outputs can be stored under `outputs/` and screenshots under `images/results/`.

## 7. Outputs

Keep representative real-run results in:

```text
outputs/
+-- predictions/
+-- evaluations/
+-- logs/
```

Avoid committing private data or unnecessarily large generated files.

## 8. Images

The `images/` directory is intended to make the project easy to understand visually.

Suggested images:

- ROSIE architecture
- data/training pipeline
- inference workflow
- terminal output
- testing results
- robotics-oriented concept diagrams

Use descriptive filenames such as:

```text
rosie-overview.png
training-pipeline.png
inference-example-01.png
test-results.png
```

## 9. Robotics Direction

A longer-term direction for ROSIE is to explore how a compact language model can participate in robotics systems.

The idea is not simply to put an LLM inside a robot. ROSIE can instead act as one component in a larger system:

```text
Human / Environment
        |
        v
   Input / Command
        |
        v
      ROSIE
        |
        +------> Intent / Interpretation
        |
        +------> Context / State
        |
        v
 Robotics Control Layer
        |
        v
 Sensors / Actuators / Robot
```

This direction will be developed experimentally and documented as the project evolves.

## 10. Reproducibility

Record, whenever applicable:

- Python version
- operating system
- CPU/GPU
- framework versions
- model name/version
- dataset version
- dataset size
- batch size
- learning rate
- number of epochs
- random seed
- training time
- validation/test results

The objective is to make experiments understandable and repeatable.

## 11. What ROSIE Is NOT

ROSIE is not presented as a replacement for large commercial LLMs.

It is a practical exploration of:

- small language models
- model training
- data preparation
- inference
- evaluation
- experimentation
- local AI
- robotics-oriented AI systems

The emphasis is on learning, engineering, testing, and documenting the process.

## 12. Project Status

**Status: Experimental / Active Development**

The repository will evolve as new experiments, scripts, tests, and robotics-oriented capabilities are added.

## 13. Roadmap

### In Progress

- [ ] Organize training and inference scripts
- [ ] Document model architecture
- [ ] Document training experiments
- [ ] Add repeatable test suite
- [ ] Add representative outputs
- [ ] Add architecture diagrams
- [ ] Document robotics direction

### Future

- [ ] Improve evaluation methodology
- [ ] Add more challenging test cases
- [ ] Investigate model efficiency
- [ ] Explore local deployment
- [ ] Connect ROSIE to robotics components
- [ ] Test ROS/robotics integration
- [ ] Document real-world robotics experiments

## 14. Repository Philosophy

The repository intentionally keeps code, experiments, outputs, and documentation together.

The objective is to show not only **what ROSIE can do**, but also:

**how it was built, how it was tested, what failed, what improved, and where the project is going.**

