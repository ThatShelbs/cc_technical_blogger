# CLAUDE.md

Guidance for Claude Code when working in this repository. 

## Project purpose

A react front end, python back end application that lets people write engaging technical blogs in their own voice. 

This solution is specialized in writing technical blogs generally covering the following topics:
 - Data Science
 - Python Programming
 - Data Visualization
 - Machine Learning
 - Causality, Experimentation, & Causal Inference
 - Leading Analytics and Data Science Professionals
 - Advanced Analytics and Data Science at Large Companies
 - AI, LLM, and Agents
 - AI/ML Platforms (AWS, Snowflake)
 - Building with Agentic Coding Tools (Claude Code, Cursor, Anti-Gravity)

## Core functionality of solution:

### User Level Functionality
- The user can upload samples of their blogs and writing as my_writing_examples which is used to help establish personalized voice, tone, soul, structure of writing
- The user can also upload samples of other people's blogs and writings to further synthesize voice, tone, soul, structure of writing
- The user can also optionally turn on web research which will run a LLM/Agent to gather best practicies in writing technical AI/ML blogs including
    - title creation 
    - writing compelling and satisfying stories
    - ensuring the structure serves the skim reader
    - incorporating humor
    - incorporating insightful work
    - building credibility and trust
    - educating by writing
- Once the configuration is ready the user can generate a voice_soul.md that the solution will now use for all project
- The voice_soul.md only has to be created once per user but can always be regenerated
- The user can build multiple persona's and give them names but has to have one selected as "on" with all the others as "off"

### Project Level Functionality
- The user will make one project per article/post/story
- There are additional dials to control target story length, how many images are generated within it, humor level, education level
- Regarding the story images
    - Every post has an initial image that is also the thumbnail for the post
    - Every post closes with a funny relevant joke or meme image 
    - Other images serve key concepts, workflows, diagrams, and other points of the subsections 
    - Images should take very much care to be relevant to the text and provide additional value to the reader for example
        - a clarifying digram
        - an illustrative data visualization 
        - a moment of humor 
        - images should source their creator (user name with model credit as well)
    - The user can redraw on any given image, to get another random image
    - When relevant, posts have key code snippets, LLM prompts, or platform screenshots
- The user is able to download the completed story optimized forone of medium.com, substack.com, gumroad.com, etc.
- Once the user is satisfied with the configuration they provide a prompt or bullet point outline of the story and the application generates it
    - ensure this is in the 'on' persona's synthesized voice tone soul structure that was generated, this is the key point of the solution if we don't pull this step off with high quality the application is a failure
    - ensure the images are placed in-line in the story


## Other details

 - use python for backend and REACT for front end
 - with python always use UV for enviornment control
 - always use smart defaults, the user should have to fill out a very minimal set of inputs to do the work but have the option for lots of customization and flexability
 - take care that this application is easy to launch with a .bat file
 - use best practicies for folder structure and file organization in this repo so humans can easily and intuitively dev on this open source application
 - after working on app always prove the functionality worked and the tool is still in good health and passing tests
 - after working on app always revisit CLAUDE.md as needed
 - ensure the repository is documented well and looks like a professional 
 - generate a logo for the solution which is a cute, savy, professional agent robot that is also a tech blogger
 - lets priortize inferno color palette for logo design and applicaiton theme
 - Make sure the application can run in day mode and night mode as themes
 - The application can connect and login to Claude via SSO

