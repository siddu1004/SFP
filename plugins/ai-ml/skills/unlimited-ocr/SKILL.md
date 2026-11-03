---
name: unlimited-ocr
description: "Parse long documents using Baidu Unlimited-OCR in one shot. Use this skill when dealing with multi-page documents that need OCR processing."
---

> Written for SFP in its own words from the project at https://github.com/baidu/Unlimited-OCR (upstream license: MIT).

# Parsing Long Documents with Baidu Unlimited-OCR

## Use this skill when
- You have a document with multiple pages that require OCR.
- You want to process the entire document in one request, leveraging cross-page context.

## What it is
Baidu Unlimited-OCR is an advanced OCR model capable of parsing ultra-long documents. It uses Sparse Reference Sliding Window Attention (SR-SWA) to handle large volumes of text efficiently, ensuring fast and accurate results without quadratic attention scaling or memory bottlenecks.

## Steps
1. **Install Required Packages**: Ensure you have the necessary Python packages installed.
   ```shell
   pip install torch==2.13.0 torchvision pillow transformers==4.52.1 huggingface-hub==0.36.0 \
     tokenizers==0.21.4 addict==2.4.0 einops==0.8.2 easydict==1.13
   ```
2. **Load the Model**: Import and load the Baidu Unlimited-OCR model.
   ```python
   import torch
   from transformers import AutoModel, AutoTokenizer

   model_name = "baidu/Unlimited-OCR-2"
   tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
   model = AutoModel.from_pretrained(model_name, trust_remote_code=True, use_safetensors=True,
                                     torch_dtype=torch.bfloat16).eval().cuda()
   ```
3. **Perform Multi-page Inference**: Use the `infer_multi` method to parse all pages of a document in one request.
   ```python
   pages = [f"your_doc/page_{i}.jpg" for i in range(1, 8)]
   text, num_tokens = model.infer_multi(tokenizer, image_files=pages,
                                        output_path="output/multi", save_results=True)
   ```
4. **Save or Process the Output**: The parsed text is returned and can be saved or further processed as needed.

## Checks
- Ensure all required packages are installed.
- Verify that the model loads correctly without errors.
- Confirm that the document pages are in the correct order before passing them to the inference method.

## Pitfalls
- **Memory Usage**: Although SR-SWA helps manage memory, ensure your system has sufficient resources for large documents.
- **Image Quality**: High-quality images yield better OCR results. Preprocess images if necessary to improve accuracy.
- **Error Handling**: Implement error handling for cases where the model fails to load or inference fails.
