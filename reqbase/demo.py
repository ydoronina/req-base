from .domain import COLLECTIONS, RequirementChange, stamp


def seed(service):
    with service.store.transaction(write=True) as db:
        if service.store.projects(db, deleted=True):
            return
        project = {**stamp("user"), **{key: [] for key in COLLECTIONS},
                   "title": "Клиентский портал", "prefix": "PORTAL", "description": "Демонстрационный проект",
                   "customer": "", "authors": [], "document_version": "1.0", "document_date": "", "locale": "ru"}
        change = RequirementChange(project, "user", "ui", "create")
        branches = [
            ("Регистрация и вход", "Approved", "Must", "доступ", [
                ("Регистрация по электронной почте", "Approved", "Must", "FR"),
                ("Подтверждение адреса", "In Review", "Must", "FR"),
                ("Восстановление пароля", "Draft", "Should", "FR"),
                ("Защита учётных данных", "Approved", "Must", "NFR"),
            ]),
            ("Управление профилем", "In Review", "Should", "профиль", [
                ("Редактирование личных данных", "Approved", "Must", "FR"),
                ("Настройка уведомлений", "Draft", "Could", "FR"),
            ]),
            ("История обращений", "Draft", "Must", "поддержка", [
                ("Просмотр списка обращений", "Draft", "Must", "FR"),
                ("Время загрузки списка", "In Review", "Should", "NFR"),
            ]),
            ("Отчётность по обращениям", "Draft", "Could", "отчёты", []),
        ]
        for title, status, priority, tag, children in branches:
            root = change.create({"title": title, "status": status, "priority": priority, "tags": [tag]}, None)
            for child, child_status, child_priority, child_type in children:
                details = {}
                if child == "Регистрация по электронной почте":
                    details = {
                        "description": "Пользователь может создать аккаунт по электронной почте и паролю. "
                                       "После отправки формы система высылает письмо со ссылкой подтверждения.",
                        "acceptance_criteria": ["Форма принимает корректный email и пароль.",
                                                "На указанный адрес приходит письмо со ссылкой.",
                                                "Повторная регистрация на тот же адрес отклоняется."],
                        "source": "Интервью с владельцем продукта",
                    }
                change.create({"title": child, "status": child_status, "priority": child_priority,
                               "type": child_type, "tags": [tag], **details}, root["id"])
        change.finish()
        registration = project["requirements"][1]
        for title, diagram_type, source, kind, linked in (
            ("Регистрация пользователя", "mermaid",
             "sequenceDiagram\n  actor User\n  User->>Portal: Submit form\n  Portal-->>User: Send confirmation", "sequence",
             [project["requirements"][0], registration]),
            ("Подтверждение email", "plantuml",
             "@startuml\nactor User\nUser -> Portal: Confirm email\nPortal --> User: Account active\n@enduml",
             "sequence", [project["requirements"][2]]),
        ):
            diagram = {**stamp("user"), "project_id": project["id"], "title": title, "type": diagram_type,
                       "source": source, "kind": kind}
            project["diagrams"].append(diagram)
            for row in linked:
                project["requirement-diagrams"].append({**stamp("user"), "project_id": project["id"],
                    "requirement_id": row["id"], "diagram_id": diagram["id"]})
        service.store.save(db, project)
