from langchain_community.retrievers import WikipediaRetriever

retriever = WikipediaRetriever()

docs = retriever.invoke("epiphron")

print(docs[0].page_content)