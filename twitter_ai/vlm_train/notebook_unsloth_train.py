from unsloth import FastVisionModel  # FastLanguageModel for LLMs
import torch

model, tokenizer = FastVisionModel.from_pretrained(
    "unsloth/Llama-3.2-11B-Vision-Instruct",
    load_in_4bit=True,  # Use 4bit to reduce memory use. False for 16bit LoRA.
    use_gradient_checkpointing="unsloth",  # True or "unsloth" for long context
)

model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=True,  # False if not finetuning vision layers
    finetune_language_layers=True,  # False if not finetuning language layers
    finetune_attention_modules=True,  # False if not finetuning attention layers
    finetune_mlp_modules=True,  # False if not finetuning MLP layers
    r=16,  # The larger, the higher the accuracy, but might overfit
    lora_alpha=16,  # Recommended alpha == r at least
    lora_dropout=0,
    bias="none",
    random_state=3407,
    use_rslora=False,  # We support rank stabilized LoRA
    loftq_config=None,  # And LoftQ
    # target_modules = "all-linear", # Optional now! Can specify a list if needed
)

from datasets import load_dataset

dataset = load_dataset("nikita-nrg/length_captchas", split="train")

instruction = """The image shows a simple measuring scale with numerical markings. An object's edge is aligned with one of these marks.
Your task is to identify the numerical value on the scale where the object ends and output that measured length as a number (using the same units as on the scale).
Provide the measurement as a rounded integer.
"""


def convert_to_conversation(sample):
    ground_truth, first_scale_value = int(sample["ground_truth"]), int(
        sample["first_scale_value"]
    )
    one_scale_value = int(first_scale_value / 2)
    if ground_truth % first_scale_value == 0:
        # Aligned with a number on the scale
        response = (
            f"I can see that the object's edge is aligned with a mark that shows the value {ground_truth}. "
            f"So, the measured length is {ground_truth}."
        )
    else:
        # Not aligned with a number on the scale
        response = (
            f"I can see that the object's edge is aligned with a mark that does not show a number. "
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


# Split the dataset into train/test sets (e.g., 80% train, 20% test)
split_data = dataset.train_test_split(test_size=0.2, seed=42)
train_dataset = split_data["train"]
test_dataset = split_data["test"]

converted_train = [convert_to_conversation(sample) for sample in train_dataset]
converted_test = [convert_to_conversation(sample) for sample in test_dataset]


### load test sample
image = dataset[0]["image"]
messages = [
    {
        "role": "user",
        "content": [{"type": "image"}, {"type": "text", "text": instruction}],
    }
]
print(messages)

### run inference on test sample
FastVisionModel.for_inference(model)  # Enable for inference!
input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
inputs = tokenizer(
    image,
    input_text,
    add_special_tokens=False,
    return_tensors="pt",
).to("cuda")

from transformers import TextStreamer

text_streamer = TextStreamer(tokenizer, skip_prompt=True)
_ = model.generate(
    **inputs,
    streamer=text_streamer,
    max_new_tokens=128,
    use_cache=True,
    temperature=1.5,
    min_p=0.1,
)


from unsloth import is_bf16_supported
from unsloth.trainer import UnslothVisionDataCollator
from trl import SFTTrainer, SFTConfig

FastVisionModel.for_training(model)  # Enable for training!


## init trainer
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    data_collator=UnslothVisionDataCollator(model, tokenizer),  # Must use!
    train_dataset=converted_train,
    args=SFTConfig(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        warmup_steps=5,
        # max_steps = 30,
        num_train_epochs=2,  # Set this instead of max_steps for full training runs
        learning_rate=2e-4,
        fp16=not is_bf16_supported(),
        bf16=is_bf16_supported(),
        logging_steps=1,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=3407,
        output_dir="outputs",
        report_to="none",  # For Weights and Biases
        # You MUST put the below items for vision finetuning:
        remove_unused_columns=False,
        dataset_text_field="",
        dataset_kwargs={"skip_prepare_dataset": True},
        dataset_num_proc=4,
        max_seq_length=2048,
    ),
)

trainer_stats = trainer.train()

FastVisionModel.for_inference(model)  # Enable for inference!

### get test sample
image = dataset[227]["image"]
messages = [
    {
        "role": "user",
        "content": [{"type": "image"}, {"type": "text", "text": instruction}],
    }
]
### run inference of trained model on test sample
input_text = tokenizer.apply_chat_template(messages, add_generation_prompt=True)
inputs = tokenizer(
    image,
    input_text,
    add_special_tokens=False,
    return_tensors="pt",
).to("cuda")

from transformers import TextStreamer

text_streamer = TextStreamer(tokenizer, skip_prompt=True)
_ = model.generate(
    **inputs,
    streamer=text_streamer,
    max_new_tokens=128,
    use_cache=True,
    temperature=1.5,
    min_p=0.1,
)
