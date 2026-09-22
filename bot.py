import json
import logging
import os
from datetime import time
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "promos.json"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "METTRE_ICI_LE_TOKEN")
AMAZON_TAG = os.environ.get("AMAZON_TAG", "techiaactu21-21")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")

POST_HOURS = [
    int(h) for h in os.environ.get("POST_HOURS", "12,18").split(",") if h.strip()
]

DISCLOSURE = (
    "\n\n_En tant que Partenaire Amazon, je perçois des commissions "
    "sur les achats remplissant les conditions requises._"
)

CATEGORIES = {
    "all": "🎯 Toutes",
    "tech": "💻 Tech",
    "maison": "🏠 Maison",
    "mode": "👟 Mode",
}


def load_promos() -> dict:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Erreur lecture promos: %s", e)
        return {"promos": []}


def build_amazon_link(lien: str) -> str:
    if "amazon.fr" in lien and "tag=" not in lien:
        sep = "&" if "?" in lien else "?"
        return f"{lien}{sep}tag={AMAZON_TAG}"
    if "amazon.fr" in lien and "tag=" in lien:
        return lien
    return lien


def format_promo(p: dict) -> str:
    lines = [f"🔥 <b>{p['titre']}</b>"]
    ligne_prix = f"💰 <b>{p['prix']}</b>"
    if p.get("prix_barre"):
        ligne_prix += f" <s>{p['prix_barre']}</s>"
    if p.get("economie"):
        ligne_prix += f"  →  📉 {p['economie']}"
    lines.append(ligne_prix)
    if p.get("note"):
        lines.append(f"ℹ️ {p['note']}")
    lines.append(f"👉 <a href=\"{build_amazon_link(p['lien'])}\">Voir l'offre</a>")
    return "\n".join(lines)


def menu_clavier() -> InlineKeyboardMarkup:
    boutons = [
        [InlineKeyboardButton("🔥 Promos du jour", callback_data="promos")],
        [
            InlineKeyboardButton("💻 Tech", callback_data="cat_tech"),
            InlineKeyboardButton("🏠 Maison", callback_data="cat_maison"),
        ],
        [
            InlineKeyboardButton("👟 Mode", callback_data="cat_mode"),
            InlineKeyboardButton("🎯 Tout voir", callback_data="cat_all"),
        ],
    ]
    return InlineKeyboardMarkup(boutons)


def promos_texte(categorie: str = "all") -> tuple[str, InlineKeyboardMarkup | None]:
    data = load_promos()
    promos = data.get("promos", [])
    if categorie != "all":
        promos = [p for p in promos if p.get("categorie") == categorie]

    if not promos:
        text = "Pas de promo pour l'instant dans cette catégorie. Reviens plus tard !"
        return text, InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀️ Retour", callback_data="menu")]]
        )

    text = "🔥 <b>Promos du jour</b>\n"
    if categorie != "all":
        text = f"🔥 <b>Promos {CATEGORIES.get(categorie, categorie)}</b>\n"
    text += "─" * 20 + "\n\n"

    boutons = []
    for i, p in enumerate(promos, 1):
        text += f"<b>{i}.</b> {format_promo(p)}\n\n"
        if "amazon.fr" in p.get("lien", ""):
            boutons.append(
                [
                    InlineKeyboardButton(
                        f"🛒 {p['titre'][:40]}",
                        url=build_amazon_link(p["lien"]),
                    )
                ]
            )

    text += f"<i>Mis à jour le {data.get('updated', 'n/a')}</i>{DISCLOSURE}"
    boutons.append([InlineKeyboardButton("◀️ Menu principal", callback_data="menu")])
    return text, InlineKeyboardMarkup(boutons)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 <b>Bienvenue sur Bons Plans du Jour !</b>\n\n"
        "Je t'envoie chaque jour les meilleures promos France "
        "(tech, maison, mode…).\n\n"
        "➡️ Clique sur un bouton ci-dessous pour commencer."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=menu_clavier(), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=menu_clavier(), parse_mode="HTML"
        )


async def cmd_promos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text, clavier = promos_texte("all")
    await update.message.reply_text(
        text, reply_markup=clavier, parse_mode="HTML", disable_web_page_preview=True
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = "📋 <b>Menu</b>\nChoisis une catégorie :"
    await update.message.reply_text(text, reply_markup=menu_clavier(), parse_mode="HTML")


async def bouton(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        await cmd_start(update, context)
        return

    if data == "promos":
        text, clavier = promos_texte("all")
    elif data.startswith("cat_"):
        text, clavier = promos_texte(data.replace("cat_", ""))
    else:
        return

    await query.edit_message_text(
        text, reply_markup=clavier, parse_mode="HTML", disable_web_page_preview=True
    )


async def job_publier(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CHANNEL_ID:
        logger.info("CHANNEL_ID vide, pas de publication auto")
        return
    data = load_promos()
    promos = data.get("promos", [])[:5]
    if not promos:
        return

    text = "☀️ <b>Bons Plans du jour</b>\n" + "─" * 20 + "\n\n"
    boutons = []
    for i, p in enumerate(promos, 1):
        text += f"<b>{i}.</b> {format_promo(p)}\n\n"
        if "amazon.fr" in p.get("lien", ""):
            boutons.append(
                [
                    InlineKeyboardButton(
                        f"🛒 {p['titre'][:40]}",
                        url=build_amazon_link(p["lien"]),
                    )
                ]
            )
    text += f"<i>{data.get('updated', '')}</i>{DISCLOSURE}"
    boutons.append(
        [InlineKeyboardButton("🤖 Ouvrir le bot", url="https://t.me/BonsPlansDuJourBot")]
    )

    try:
        await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            reply_markup=InlineKeyboardMarkup(boutons),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info("Promos publiées dans %s", CHANNEL_ID)
    except Exception as e:
        logger.error("Erreur publication: %s", e)


def main() -> None:
    if BOT_TOKEN == "METTRE_ICI_LE_TOKEN":
        raise SystemExit("BOT_TOKEN manquant — configure la variable d'environnement")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("promos", cmd_promos))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CallbackQueryHandler(bouton))

    job_queue = app.job_queue
    if job_queue:
        for h in POST_HOURS:
            job_queue.run_daily(
                job_publier,
                time=time(hour=h, minute=0),
                name=f"post_{h}h",
            )
        logger.info("Publications programmées à: %s", POST_HOURS)

    logger.info("Bot démarré — Bons Plans du Jour")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
