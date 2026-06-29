import os
import gradio as gr

# Read the built frontend HTML
with open("index.html", "r", encoding="utf-8") as f:
    html_content = f.read()

# Ensure assets paths are correct for HF Spaces root
html_content = html_content.replace('href="/assets/', 'href="./assets/')
html_content = html_content.replace('src="/assets/', 'src="./assets/')

demo = gr.Interface(
    fn=None,
    inputs=None,
    outputs=gr.HTML(html_content),
    title="KinematicsAI Lab v7.0",
    description="Stroke Rehabilitation Kinematic Analysis System"
)

if __name__ == "__main__":
    demo.launch()
