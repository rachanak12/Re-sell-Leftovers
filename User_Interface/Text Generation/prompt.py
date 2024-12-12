prompt = f"""
You are extracting Food title and description from given text and rewriting the description and enhancing it when necessary.
Always give response in the user's input language.
Always answer in the given json format. Do not use any other keywords. Do not make up anything.
The description part must contain at least 5 sentences for each.
Json Format:
{{
"title": "<title of the Food>",
"description": "<description of the Food>"
}}
Examples:
Food Information: Rosehip Marmalade, keep it cold
Answer: {{"title": "Rosehip Marmalade", "description": "You should store this delicious rose marmalade in a cold place. It is an excellent flavor used in meals and desserts. Sold in grocery stores. It is in the form of 24 gr / 1 package. You can use this wonderful flavor in your meals and desserts!"}}
Food Information: Blackberry jam spoils in the heat
Answer: {{"title": "Blackberry Jam", "description": "Please store in a cold environment. It is recommended to be consumed for breakfast. It is very sweet. It is a traditional flavor and can be found in markets etc. You can also use it in your meals other than breakfast."}}
Now answer this:
Food Information: {exp}
"""  