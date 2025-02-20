from unsloth import FastVisionModel, is_bf16_supported
import torch
import re
from datasets import load_dataset
from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig

# Load model and tokenizer in 4bit with gradient checkpointing
model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Llama-3.2-11B-Vision-Instruct",
    load_in_4bit=True,
    use_gradient_checkpointing="unsloth",
)

# Apply PEFT (LoRA) to model with vision and language finetuning enabled
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=True,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=16,
    lora_alpha=16,
    lora_dropout=0,
    bias="none",
    random_state=3407,
    use_rslora=False,
    loftq_config=None,
)

# Load dataset and define instruction prompt
dataset = load_dataset("nikita-nrg/length_captchas", split="train")
instruction = (
    "The image shows a simple measuring scale with numerical markings. An object's edge is aligned with one of these marks.\n"
    "Your task is to identify the numerical value on the scale where the object ends and output that measured length as a number (using the same units as on the scale).\n"
    "Provide the measurement as a rounded integer."
)


# Convert dataset sample to conversation format for training
def convert_to_conversation(sample):
    ground_truth = int(sample["ground_truth"])
    first_scale_value = int(sample["first_scale_value"])
    one_scale_value = int(first_scale_value / 2)
    if ground_truth % first_scale_value == 0:
        response = (
            f"I can see that the object's edge is aligned with a mark that shows the value {ground_truth}. "
            f"So, the measured length is {ground_truth}."
        )
    else:
        response = (
            "I can see that the object's edge is aligned with a mark that does not show a number. "
            "To determine the measured length, I first need to identify one step of the scale. "
            f"I see that the first non-zero value on the scale is {first_scale_value}. There are two steps from 0 to this value, "
            f"so one scale step is {first_scale_value} / 2 = {one_scale_value}. "
            f"Next, I find the closest marked value, which is {ground_truth - one_scale_value}. "
            f"Adding one scale step: {ground_truth - one_scale_value} + {one_scale_value} = {ground_truth}, "
            f"so the measured length is {ground_truth}."
        )
    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": instruction},
                {"type": "image", "image": sample["image"]},
            ],
        },
        {"role": "assistant", "content": [{"type": "text", "text": response}]},
    ]
    return {"messages": conversation}


# Split dataset into train/test sets and prepare training data
split_data = dataset.train_test_split(test_size=0.2, seed=42)
train_dataset = split_data["train"]
test_dataset = split_data["test"]

converted_train = [convert_to_conversation(sample) for sample in train_dataset]
# Note: converted_test is not used for evaluation since we need ground truth separately.
converted_test = [convert_to_conversation(sample) for sample in test_dataset]

# Initialize trainer for training
FastVisionModel.for_training(model)
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    data_collator=UnslothVisionDataCollator(model, tokenizer),
    train_dataset=converted_train,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        num_train_epochs=2,  # Total number of epochs
        learning_rate=2e-4,
        fp16=not is_bf16_supported(),
        bf16=is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs",
        report_to="none",
        remove_unused_columns=False,
        dataset_text_field="",
        dataset_kwargs={"skip_prepare_dataset": True},
        dataset_num_proc=4,
        max_seq_length=2048,
    ),
)

# Training and evaluation loop: after each epoch, evaluate on test set and save if improved
num_epochs = trainer.args.num_train_epochs
best_accuracy = 0.0

for epoch in range(num_epochs):
    print(f"\nEpoch {epoch+1}/{num_epochs}")
    # Train for one epoch; resume from checkpoint if not the first epoch
    trainer.args.num_train_epochs = 1
    if epoch == 0:
        trainer.train()
    else:
        trainer.train(resume_from_checkpoint=True)

    # Switch to inference mode for evaluation
    FastVisionModel.for_inference(model)
    correct = 0
    total = 0

    # Evaluate on each sample in the original test dataset
    for sample in test_dataset:
        ground_truth = int(sample["ground_truth"])
        image = sample["image"]
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {"type": "image", "image": image},
                ],
            }
        ]
        input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
        inputs = tokenizer(
            image,
            input_text,
            add_special_tokens=False,
            return_tensors="pt",
        ).to("cuda")
        outputs = model.generate(
            **inputs,
            max_new_tokens=128,
            use_cache=True,
            temperature=1.5,
            min_p=0.1,
        )
        sample_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        nums = (
            re.findall(r"\d+", sample_response) if sample_response is not None else []
        )
        extracted_result = int(nums[-1]) if nums else ""
        if extracted_result == ground_truth:
            correct += 1
        total += 1

    accuracy = correct / total if total > 0 else 0
    print(f"Test accuracy: {accuracy:.4f}")

    # Save model if test accuracy improved
    if accuracy > best_accuracy:
        best_accuracy = accuracy
        model.push_to_hub_merged(
            "YOUR_USERNAME/unsloth_finetune", tokenizer, token="PUT_HERE"
        )
        print("Model saved to hub.")

    # Switch back to training mode for the next epoch
    FastVisionModel.for_training(model)
