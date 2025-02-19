from datasets import load_dataset

dataset = load_dataset("nikita-nrg/length_captchas", split="train")

instruction = """
The image shows a simple measuring scale with numerical markings. An object's edge is aligned with one of these marks.
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


converted_dataset = [convert_to_conversation(sample) for sample in dataset]
