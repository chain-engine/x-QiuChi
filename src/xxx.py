from main import create_server, tool, resource, prompt
server = create_server("MyServer")

@tool(category="math")
def add(a: float, b: float) -> float:
    '''Add two numbers.'''
    return a + b

server.run()