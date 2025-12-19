import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from datetime import datetime
from openpyxl import Workbook

from config import BOT_TOKEN, ADMIN_IDS, ALMACENERO_IDS
from database import init_db, connect

# ================= BOT =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ================= ROLES =================
def es_admin(uid):
    return uid in ADMIN_IDS

def es_almacenero(uid):
    return uid in ALMACENERO_IDS or es_admin(uid)

# ================= CONSTANTES =================
UBICACIONES = [
    "Entrada 4to Piso",
    "Pasadizo 4to Piso",
    "Izquierda 4to Piso",
    "Medio 4to Piso",
    "Fondo 4to Piso",
    "Derecha 4to Piso"
]

# ================= ESTADOS =================
class RegistroCaja(StatesGroup):
    codigo = State()
    marca = State()
    color = State()
    cantidad = State()
    ubicacion = State()

class AjusteStock(StatesGroup):
    codigo = State()
    tipo = State()
    cantidad = State()

class MoverCaja(StatesGroup):
    codigo = State()
    nueva_ubicacion = State()

class VerStock(StatesGroup):
    tipo = State()
    valor = State()

# ================= MENÚS =================
def main_menu(uid):
    botones = [
        [KeyboardButton(text="🔍 Ver stock")],
        [KeyboardButton(text="➖➕ Ajustar stock")],
        [KeyboardButton(text="🔁 Mover cajas")]
    ]

    if es_admin(uid):
        botones.insert(0, [KeyboardButton(text="➕ Registrar caja")])
        botones.append([KeyboardButton(text="📊 Exportar Excel")])
        botones.append([KeyboardButton(text="📜 Ver historial")])

    return ReplyKeyboardMarkup(
        keyboard=botones,
        resize_keyboard=True
    )

def menu_ubicaciones():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=u)] for u in UBICACIONES],
        resize_keyboard=True
    )

def menu_filtro_stock():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Por marca")],
            [KeyboardButton(text="🔎 Por código")],
            [KeyboardButton(text="⬅️ Volver")]
        ],
        resize_keyboard=True
    )

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📦 Sistema de Stock de Cajas",
        reply_markup=main_menu(message.from_user.id)
    )

# ================= REGISTRAR CAJA =================
@dp.message(lambda m: m.text == "➕ Registrar caja")
async def registrar_inicio(message: Message, state: FSMContext):
    if not es_admin(message.from_user.id):
        return
    await state.set_state(RegistroCaja.codigo)
    await message.answer("📦 Código de la caja:")

@dp.message(RegistroCaja.codigo)
async def registrar_codigo(message: Message, state: FSMContext):
    await state.update_data(codigo=message.text)
    await state.set_state(RegistroCaja.marca)
    await message.answer("🏷 Marca:")

@dp.message(RegistroCaja.marca)
async def registrar_marca(message: Message, state: FSMContext):
    await state.update_data(marca=message.text)
    await state.set_state(RegistroCaja.color)
    await message.answer("🎨 Color (código):")

@dp.message(RegistroCaja.color)
async def registrar_color(message: Message, state: FSMContext):
    await state.update_data(color=message.text)
    await state.set_state(RegistroCaja.cantidad)
    await message.answer("🔢 Cantidad:")

@dp.message(RegistroCaja.cantidad)
async def registrar_cantidad(message: Message, state: FSMContext):
    await state.update_data(cantidad=int(message.text))
    await state.set_state(RegistroCaja.ubicacion)
    await message.answer("📍 Ubicación:", reply_markup=menu_ubicaciones())

@dp.message(RegistroCaja.ubicacion)
async def registrar_final(message: Message, state: FSMContext):
    d = await state.get_data()
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cajas (codigo, marca, color, cantidad, ubicacion, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        d["codigo"], d["marca"], d["color"],
        d["cantidad"], message.text,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))
    conn.commit()
    conn.close()
    await state.clear()
    await message.answer(
        "✅ Caja registrada correctamente",
        reply_markup=main_menu(message.from_user.id)
    )

# ================= VER STOCK (CON FILTRO) =================
@dp.message(lambda m: m.text == "🔍 Ver stock")
async def ver_stock_inicio(message: Message, state: FSMContext):
    await state.set_state(VerStock.tipo)
    await message.answer(
        "¿Cómo deseas buscar el stock?",
        reply_markup=menu_filtro_stock()
    )

@dp.message(VerStock.tipo)
async def ver_stock_tipo(message: Message, state: FSMContext):
    if message.text == "⬅️ Volver":
        await state.clear()
        await message.answer(
            "Menú principal",
            reply_markup=main_menu(message.from_user.id)
        )
        return

    await state.update_data(tipo=message.text)
    await state.set_state(VerStock.valor)
    await message.answer("✏️ Escribe el valor a buscar:")

@dp.message(VerStock.valor)
async def ver_stock_resultado(message: Message, state: FSMContext):
    data = await state.get_data()
    conn = connect()
    cur = conn.cursor()

    if "marca" in data["tipo"].lower():
        cur.execute("""
            SELECT codigo, marca, color, cantidad, ubicacion
            FROM cajas
            WHERE marca LIKE ?
        """, (f"%{message.text}%",))
    else:
        cur.execute("""
            SELECT codigo, marca, color, cantidad, ubicacion
            FROM cajas
            WHERE codigo = ?
        """, (message.text,))

    filas = cur.fetchall()
    conn.close()
    await state.clear()

    if not filas:
        await message.answer(
            "❌ No se encontró stock.",
            reply_markup=main_menu(message.from_user.id)
        )
        return

    texto = "📦 RESULTADO DE BÚSQUEDA\n\n"
    for c, m, col, q, u in filas:
        texto += (
            f"📦 Código: {c}\n"
            f"🏷 Marca: {m}\n"
            f"🎨 Color: {col}\n"
            f"🔢 Cantidad: {q}\n"
            f"📍 Ubicación: {u}\n"
            "---------------------\n"
        )

    for i in range(0, len(texto), 4000):
        await message.answer(
            texto[i:i+4000],
            reply_markup=main_menu(message.from_user.id)
        )

# ================= AJUSTAR STOCK =================
@dp.message(lambda m: m.text == "➖➕ Ajustar stock")
async def ajuste_inicio(message: Message, state: FSMContext):
    if not es_almacenero(message.from_user.id):
        return
    await state.set_state(AjusteStock.codigo)
    await message.answer("📦 Código de la caja:")

@dp.message(AjusteStock.codigo)
async def ajuste_codigo(message: Message, state: FSMContext):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT cantidad FROM cajas WHERE codigo = ?", (message.text,))
    fila = cur.fetchone()
    conn.close()

    if not fila:
        await state.clear()
        await message.answer(
            "❌ Caja no encontrada",
            reply_markup=main_menu(message.from_user.id)
        )
        return

    await state.update_data(codigo=message.text, actual=fila[0])
    await state.set_state(AjusteStock.tipo)

    teclado = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Sumar")],
            [KeyboardButton(text="➖ Restar")]
        ],
        resize_keyboard=True
    )

    await message.answer("¿Qué deseas hacer?", reply_markup=teclado)

@dp.message(AjusteStock.tipo)
async def ajuste_tipo(message: Message, state: FSMContext):
    await state.update_data(tipo=message.text)
    await state.set_state(AjusteStock.cantidad)
    await message.answer("🔢 Cantidad:")

@dp.message(AjusteStock.cantidad)
async def ajuste_final(message: Message, state: FSMContext):
    d = await state.get_data()
    cantidad = int(message.text)
    nuevo = d["actual"] + cantidad if "Sumar" in d["tipo"] else d["actual"] - cantidad

    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE cajas SET cantidad=? WHERE codigo=?", (nuevo, d["codigo"]))
    cur.execute("""
        INSERT INTO historial (usuario, accion, codigo, cantidad, fecha)
        VALUES (?, ?, ?, ?, ?)
    """, (
        message.from_user.username,
        d["tipo"],
        d["codigo"],
        cantidad,
        datetime.now().strftime("%Y-%m-%d %H:%M")
    ))
    conn.commit()
    conn.close()
    await state.clear()

    await message.answer(
        "✅ Stock actualizado correctamente",
        reply_markup=main_menu(message.from_user.id)
    )

# ================= MOVER CAJAS =================
@dp.message(lambda m: m.text == "🔁 Mover cajas")
async def mover_inicio(message: Message, state: FSMContext):
    await state.set_state(MoverCaja.codigo)
    await message.answer("📦 Código de la caja:")

@dp.message(MoverCaja.codigo)
async def mover_codigo(message: Message, state: FSMContext):
    await state.update_data(codigo=message.text)
    await state.set_state(MoverCaja.nueva_ubicacion)
    await message.answer("📍 Nueva ubicación:", reply_markup=menu_ubicaciones())

@dp.message(MoverCaja.nueva_ubicacion)
async def mover_final(message: Message, state: FSMContext):
    d = await state.get_data()
    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE cajas SET ubicacion=? WHERE codigo=?", (message.text, d["codigo"]))
    conn.commit()
    conn.close()
    await state.clear()

    await message.answer(
        "✅ Caja movida correctamente",
        reply_markup=main_menu(message.from_user.id)
    )

# ================= EXCEL =================
@dp.message(lambda m: m.text == "📊 Exportar Excel")
async def exportar_excel(message: Message):
    if not es_admin(message.from_user.id):
        return

    wb = Workbook()
    ws = wb.active
    ws.append(["Código", "Marca", "Color", "Cantidad", "Ubicación"])

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT codigo, marca, color, cantidad, ubicacion FROM cajas")
    for fila in cur.fetchall():
        ws.append(fila)
    conn.close()

    archivo = "stock.xlsx"
    wb.save(archivo)

    await message.answer_document(
        open(archivo, "rb"),
        reply_markup=main_menu(message.from_user.id)
    )

# ================= HISTORIAL =================
@dp.message(lambda m: m.text == "📜 Ver historial")
async def ver_historial(message: Message):
    if not es_admin(message.from_user.id):
        return

    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT usuario, accion, codigo, cantidad, fecha
        FROM historial
        ORDER BY fecha DESC
    """)
    filas = cur.fetchall()
    conn.close()

    if not filas:
        await message.answer(
            "📜 No hay movimientos registrados.",
            reply_markup=main_menu(message.from_user.id)
        )
        return

    texto = "📜 HISTORIAL\n\n"
    for u, a, c, q, f in filas:
        texto += f"{f} | {u} | {a} | {c} ({q})\n"

    for i in range(0, len(texto), 4000):
        await message.answer(
            texto[i:i+4000],
            reply_markup=main_menu(message.from_user.id)
        )

# ================= MAIN =================
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
