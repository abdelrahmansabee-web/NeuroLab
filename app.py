import os
import gradio as gr

# Read the built frontend HTML
with open("index.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# Ensure assets paths are correct for HF Spaces root
html_content = html_content.replace('href="/assets/', 'href="./assets/')
html_content = html_content.replace('src="/assets/', 'src="./assets/')

with gr.Blocks(title="KinematicsAI Lab v7.0") as demo:
    gr.HTML(html_content)

if __name__ == "__main__":
    demo.launch()
