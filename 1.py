from pymodbus.client.sync import ModbusSerialClient

# Khởi tạo client Modbus RTU
client = ModbusSerialClient(
    method='rtu',
    port='COM6',
    baudrate=9600,
    stopbits=1,
    bytesize=8,
    parity='N',
    timeout=1
)

# Kết nối
if client.connect():
    print("✅ Kết nối thành công!")

    # Đọc thanh ghi D0 và D1 (địa chỉ 0, số lượng 2)
    # Ghi TRUE (bật) cho Y0, tức là address 1280
    response = client.write_coil(address=2049, value=False, unit=1)
    print("\n📥 Đọc X0 (address=1024)")
    x = client.read_discrete_inputs(address=1027, count=1, unit=1)
    if not x.isError():
        print("X0 =", x.bits[0])
    client.write_coil(address=2048, value=True, unit=1)
    print("\n📥 Đọc M0 (address=0)")
    m = client.read_coils(address=2048, count=1, unit=1)
    if not m.isError():
        print("M0 =", m.bits[0])
    client.write_coil(address=1280, value=False, unit=1)
    print("\n📥 Đọc Y0 (address=0)")
    y = client.read_coils(address=1280, count=1, unit=1)
    if not m.isError():
        print("y0 =", y.bits[0])
    result = client.write_register(address=4107, value=2, unit=1)

    if result.isError():
        print("❌ Lỗi khi ghi dữ liệu:", result)
    else:
        print("✅ Ghi dữ liệu thành công vào D100")

    client.close()
else:
    print("❌ Không thể kết nối đến PLC.")
