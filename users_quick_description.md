# Agent-based Information System for Personalized arXiv Publication Monitorin, Filtering and Recommendation
This system is designed to monitor arXiv for new publications and filter them based on user preferences and expressed natural language goal. It uses combination of classical content-based filtering and LLM-based agents. Main feature is notification system that notifies user about new publications that match their preferences and goal.Second less important feature is liked papers move into personal library where user can read them later and press the button for system to explain based on the set level in settigns.

## Technologies and first vision how it should look like.
The whole application is modular and api-based. 

The system is composed of three different sub-systems.
1. Web UI - this part is the "terminal" of the app. 
It has three pages:
path - "/"
front page is description of what the app about.
path - "/dashboard"
containing feed of filtered papers.
page - "/terminal"
Where filtering settings can be set up.
- fitlering
	1. Categories
	2. Authors
	3. Topics
	4. Filtering goal, purpose what to filter
- personal library
    1. On what level publications should be explaind
        i.e. "explain it like I am a professional/student/kid"
page - "/library"
Where liked papers travel and where user can read and ask for explanation
2. Filtering pipeline
    2.1 It must call the scrapper. Retrieve the list of last day publications using predefined settings.
    2.2 It must save the list of publications into the database.
    2.3 It must apply to parallel operations okapi BM25 lexical search and SPECTER2 for the semantic similarity.
    2.4 It must combine the results and create the final list of papers that should be passed to the agentic system.
    2.5 It must save the list of papers into the database.
    2.6 It must pass the list to agentic system for final TOP5-10 paper selection.
3. Agentic system (this must be thoroughtly improved)
This should be API callable server, which takes the settings from the Web UI and scrapped documents. 
	The architecture should be based on langchain and langraph agents. The main orchestrator is responsible for calling the right agent and for decision making process.
		The subagents are:
		1. Goal distiller - takes the filtering goal and defines requirements what system has to filter. (Called once.)
		2. Evaluator - takes scrapped papers and evaluates does the paper satisfies what user asked.
		3. Critique - checks whether evaluator did what it supposed to do, creates the answer why it was filtered and provides the explanation for explainer if filtered out then it gets passed. 
		4. Explainer - takes the material provided from critique and prepares the information for the explanation why it is relevant and satisfies the prompt to provide it then for web UI.
		5. Top 3 paper - the seperate list which generates what will be sent as notification and recommender for today to the user. ( It might be simple ranking logic)
	Feedback logic memory/state - the list of disliked papers and reason, this travels into the critique prompt, but the summary of it. 
		After passing each paper through the relevance the system generates final list of relevant papers and provides it to web ui.
3. Scrapper
Also API based server or even service which scrapes today papers by given category, authors and topics. And provides to the agentic system for filtering.
4. Database
It is for the user, papers, runs, user settings, feedback and more. Also basic auth is required. 
5. Scheduling and notifier
System for notifying and presenting the material that has been filtered.