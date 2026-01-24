from llama_cpp import Llama
import json
import yaml

def load_model(model_path: str):
    """Load a GGUF model using llama.cpp"""
    return Llama(
        model_path=model_path,
        n_ctx=4096,
        n_threads=16,
        n_gpu_layers=-1,  # offload all layers to GPU
        verbose=False,
    )

def unload_model(llm):
    """Unload model and free memory"""
    del llm

def load_prompts(yaml_path: str):
    """Load prompts from a YAML file"""
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def extract_names(text: str, llm: Llama, prompts_path: str = 'prompts.yaml'):
    """Extract person names from text using LLM"""
    prompts = load_prompts(prompts_path)
    prompt = prompts['extract_names'].format(text=text)

    response = llm(
        prompt,
        max_tokens=256,
        temperature=0.3,
        stop=["</s>", "\n\n"],
    )

    # Parse the response
    if isinstance(response, dict) and 'choices' in response:
        response_text = response['choices'][0]['text'].strip()
    elif isinstance(response, str):
        response_text = response.strip()
    else:
        response_text = str(response).strip()

    try:
        names = json.loads(response_text)
        return names if isinstance(names, list) else []
    except json.JSONDecodeError:
        print(f"Failed to parse LLM response as JSON: {response_text}")
        return []
