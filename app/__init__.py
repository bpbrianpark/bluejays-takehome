from dotenv import load_dotenv
from flask import Flask

from app.config import Config

load_dotenv()


def create_app(config_object: type | None = None) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_object or Config)

    from app.extensions import init_extensions

    init_extensions(app)

    from app.context_processors import register_context_processors

    register_context_processors(app)

    from app.blueprints.leaders import leaders_bp
    from app.blueprints.main import main_bp
    from app.blueprints.players import players_bp
    from app.blueprints.standings import standings_bp
    from app.blueprints.teams import teams_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(standings_bp)
    app.register_blueprint(teams_bp)
    app.register_blueprint(players_bp)
    app.register_blueprint(leaders_bp)

    return app
