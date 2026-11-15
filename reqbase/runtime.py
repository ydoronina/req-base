from .rendering import Documents, Renderer
from .service import Service

service = Service()
renderer = Renderer(service.store)
documents = Documents(service, renderer)
