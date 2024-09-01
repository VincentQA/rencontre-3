import streamlit as st
from openai import OpenAI
import json

# Initialisation du client OpenAI avec les clés API et les identifiants des assistants
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ASSISTANT_ID_ECRIVAIN = st.secrets["ASSISTANT_ID_ECRIVAIN"]
ASSISTANT_ID_SCENARISTE = st.secrets["ASSISTANT_ID_SCENARISTE"]

client = OpenAI(api_key=OPENAI_API_KEY)

# Initialisation de l'état de la session pour stocker l'historique des conversations et les threads
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "thread_id_ecrivain" not in st.session_state:
    st.session_state.thread_id_ecrivain = None

if "thread_id_scenariste" not in st.session_state:
    st.session_state.thread_id_scenariste = None

if "plan" not in st.session_state:
    st.session_state.plan = ""

# Pré-prompts pour le scénariste et l'écrivain
scenariste_preprompt = """
Tu es un scénariste expérimenté. Ton travail consiste à créer un plan détaillé pour le Chapitre 1, Checkpoint 1. 
Ce plan doit inclure les éléments suivants :
1. Une brève introduction pour contextualiser le chapitre.
2. Les événements principaux qui doivent se produire dans ce chapitre.
3. Les choix critiques que le lecteur devra faire.
4. Une conclusion pour ce checkpoint.

Assure-toi d'être clair et exhaustif dans ton plan.
"""

user_preprompt = """
Tu es un romancier de style nouvelle romance.
Prends le temps d'avancer dans l'histoire et surtout de tenir compte des choix du lecteur dans ta réponse. 
Avant de commencer la rédaction, ouvre et apprends les informations du chapitre en cours dans tes knowledges. 
Je veux que tu appliques sans exception les points de l'auteur :
A. Le chapitre doit obligatoirement inclure (exemple : La présentation de Luc par Léa, il faut que tu intègres alors à la demande de l'auteur une description de Luc en suivant les instructions sur comment le décrire).
B. Le chapitre ne peut inclure (exemple : si une discussion entre Luc et Léa est interdite, à aucun moment tu as le droit de créer une interaction entre eux).
C. Choix du lecteur durant le chapitre (il est important de poser à la lettre au mot près les choix du lecteur, mais il faut que ce soit dans un contexte pertinent. Propose une histoire cohérente avec des choix dans un contexte cohérent. Si le choix est une tenue, propose-le quand elle fait son sac ou en sortie de douche et surtout évite les répétitions).
N'oublie pas, tu dois respecter coûte que coûte ce que tu dois inclure mais surtout ne pas inclure dans le chapitre. 
Évite toute répétition avec ce que tu as déjà écrit. Ton rôle est de présenter une histoire cohérente jusqu'au choix et surtout d'éviter les répétitions. Chacune de tes interventions doit faire au minimum 4 gros paragraphes. 
S'il ne reste plus qu'une interaction dans le chapitre, tu dois lancer le chapitre suivant dans ta réponse et donc ouvrir également le document en question.
"""

# Fonction pour générer le plan avec le scénariste
def generate_plan():
    if st.session_state.thread_id_scenariste is None:
        thread = client.beta.threads.create()
        st.session_state.thread_id_scenariste = thread.id

    # Envoyer le pré-prompt au scénariste sous forme de message
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id_scenariste,
        role="user",
        content=scenariste_preprompt
    )

    # Créer et exécuter le run du scénariste
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id_scenariste,
        assistant_id=ASSISTANT_ID_SCENARISTE
    )

    # Attendre la fin du run en vérifiant son statut via une boucle
    while True:
        run_status = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id_scenariste,
            run_id=run.id
        )
        if run_status.status in ["completed", "failed", "cancelled"]:
            break

    if run_status.status == "completed":
        # Obtenir tous les messages de la thread après exécution
        thread_messages = client.beta.threads.messages.list(st.session_state.thread_id_scenariste)
        messages = list(thread_messages)
        st.write(messages)  # Afficher tous les messages pour le diagnostic
        if messages:
            # Extraire le texte directement
            last_message = messages[-1]
            if last_message.content:
                st.session_state.plan = last_message.content[0].text.value
                # Afficher le plan au lecteur pour visualisation
                st.markdown("### Plan généré par le scénariste :")
                st.markdown(st.session_state.plan)
    else:
        st.error("Le plan n'a pas pu être généré.")

# Fonction pour démarrer l'histoire avec le plan du scénariste
def commence_histoire_avec_plan():
    generate_plan()

    if not st.session_state.plan:
        st.error("Le plan n'a pas été généré correctement.")
        return

    if st.session_state.thread_id_ecrivain is None:
        thread = client.beta.threads.create()
        st.session_state.thread_id_ecrivain = thread.id

    full_prompt = f"{st.session_state.plan}\n\n{user_preprompt}"
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id_ecrivain,
        role="user",
        content=full_prompt
    )

    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id_ecrivain,
        assistant_id=ASSISTANT_ID_ECRIVAIN,
        stream=True
    )

    assistant_reply_box = st.empty()
    assistant_reply = ""

    # Stream la réponse de l'écrivain en gérant les types d'événements
    for event in run:
        if isinstance(event, ThreadMessageDelta):
            if hasattr(event.data.delta.content[0], 'text'):
                assistant_reply_box.empty()
                assistant_reply += event.data.delta.content[0].text.value
                assistant_reply_box.markdown(assistant_reply)

    # Vérifier le statut du run après le streaming
    run_status = client.beta.threads.runs.retrieve(
        thread_id=st.session_state.thread_id_ecrivain,
        run_id=run.id
    )

    if run_status.status == "completed":
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply})
        st.success("L'histoire est prête !")
    else:
        st.error("L'écrivain n'a pas pu terminer l'histoire.")

# En-tête et titre de l'application
st.title("🎾 Rencontre sur le court ❤️")
st.subheader("Une aventure interactive où vos choix façonnent l'histoire")

# Affichage des messages de l'historique de conversation
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Boîte de dialogue pour l'entrée utilisateur et processus de streaming
if user_query := st.chat_input("Vous :"):
    if st.session_state.thread_id_ecrivain is None:
        thread = client.beta.threads.create()
        st.session_state.thread_id_ecrivain = thread.id

    with st.chat_message("user"):
        st.markdown(user_query)

    st.session_state.chat_history.append({"role": "user", "content": user_query})

    commence_histoire_avec_plan()