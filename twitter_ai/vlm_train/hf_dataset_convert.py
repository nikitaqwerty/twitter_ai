from datasets import load_dataset

dataset = load_dataset("nikita-nrg/length_captchas", split="train")

instruction = """
The image shows a simple measuring scale with numerical markings. An object’s edge is aligned with one of these marks.  
Your task is to identify the numerical value on the scale where the object ends and output that measured length as a number (in the same units indicated on the scale). 
Provide the measurement as a round integer number in your answer.
"""


def convert_to_conversation(sample):
    ground_truth, first_scale_value = int(sample["ground_truth"]), int(
        sample["first_scale_value"]
    )
    one_scale_value = int(first_scale_value / 2)
    if ground_truth % first_scale_value == 0:
        # aligned with a number on scale
        response = f"""I can see that the object edge is aligned with a mark that has a value {ground_truth} on top. 
        So the measured length is a {ground_truth}"""
    else:
        # not aligned with a number on scale
        response = f"""I can see that the object edge is aligned with a mark that has no value on top. 
To provide the measured length first I need to identify one step of the scale length. 
I see that first non-zero value on the scale is {first_scale_value}. There are two steps between zero and first value.\
So I can derive one scale value as  {first_scale_value} / 2 = {one_scale_value}
Now I can get an answer as the closest mark with number on top added to one scale value. I see the closest mark with number value is {ground_truth-one_scale_value}. 
To derive a final answer simply add one scale value to found closest mark with number value: {ground_truth-one_scale_value} + {one_scale_value} = {ground_truth}
So the measured length is a {ground_truth}
"""

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
