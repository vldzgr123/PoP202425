from OpenSSL import crypto
import sys
from datetime import datetime

def verify_cert_chain(cert_path, intermediate_path, root_path):
    try:
        print("\n=== Загрузка сертификатов ===")
        
        def load_cert(filepath):
            with open(filepath, 'rb') as f:
                cert_data = f.read()
                if not cert_data:
                    raise ValueError(f"Файл сертификата {filepath} пуст")
                return crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
        
        cert = load_cert(cert_path)
        intermediate = load_cert(intermediate_path)
        root = load_cert(root_path)

        print(f"✓ Сертификат сервиса: {cert.get_subject().CN}")
        print(f"✓ Промежуточный сертификат: {intermediate.get_subject().CN}")
        print(f"✓ Корневой сертификат: {root.get_subject().CN}")

        print("\n=== Проверка временных рамок ===")
        current_time = datetime.utcnow()
        
        def check_validity(cert, name):
            not_before = datetime.strptime(cert.get_notBefore().decode('ascii'), '%Y%m%d%H%M%SZ')
            not_after = datetime.strptime(cert.get_notAfter().decode('ascii'), '%Y%m%d%H%M%SZ')
            print(f"{name}: {not_before} - {not_after}")
            if current_time < not_before:
                raise ValueError(f"Сертификат {name} еще не действителен")
            if current_time > not_after:
                raise ValueError(f"Сертификат {name} просрочен")
            print(f"✓ {name}: временные рамки OK")
        
        check_validity(root, "Корневой сертификат")
        check_validity(intermediate, "Промежуточный сертификат")
        check_validity(cert, "Сертификат сервиса")

        print("\n=== Проверка цепочки подписей ===")
        
        store = crypto.X509Store()
        if store is None:
            raise RuntimeError("Не удалось создать X509Store")
        
        store.add_cert(root)
        
        store_ctx = crypto.X509StoreContext(store, intermediate)
        try:
            store_ctx.verify_certificate()
            print("✓ Промежуточный сертификат подписан корневым")
        except crypto.X509StoreContextError as e:
            raise ValueError(f"Промежуточный сертификат не подписан корневым: {e}")


        store.add_cert(intermediate) 
        store_ctx = crypto.X509StoreContext(store, cert)
        try:
            store_ctx.verify_certificate()
            print("✓ Сертификат сервиса подписан промежуточным")
        except crypto.X509StoreContextError as e:
            raise ValueError(f"Сертификат сервиса не подписан промежуточным: {e}")

        print("\n=== Проверка полной цепочки ===")
        full_store = crypto.X509Store()
        full_store.add_cert(root)
        
        store_ctx = crypto.X509StoreContext(
            full_store,
            cert,
            [intermediate] 
        )
        
        try:
            store_ctx.verify_certificate()
            print("✓ Полная цепочка сертификатов валидна")
            return True
        except crypto.X509StoreContextError as e:
            raise ValueError(f"Ошибка проверки цепочки: {e}")

    except Exception as e:
        print(f"\n× Критическая ошибка: {str(e)}")
        return False

def print_cert_details(cert_path, name):
    try:
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
            if not cert_data:
                print(f"Файл сертификата {cert_path} пуст")
                return
            
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert_data)
            if cert is None:
                print(f"Не удалось загрузить сертификат из {cert_path}")
                return
        
        print(f"\nДетали сертификата {name}:")
        print(f"Subject: {cert.get_subject().CN}")
        print(f"Issuer: {cert.get_issuer().CN}")
        print(f"Серийный номер: {cert.get_serial_number():X}")
        print(f"Алгоритм подписи: {cert.get_signature_algorithm().decode('ascii')}")
        print(f"Действителен: {cert.get_notBefore().decode('ascii')} - {cert.get_notAfter().decode('ascii')}")
    except Exception as e:
        print(f"Ошибка при анализе сертификата {name}: {str(e)}")

if __name__ == "__main__":
    print("="*60)
    print("ПОЛНАЯ ПРОВЕРКА ЦЕПОЧКИ СЕРТИФИКАТОВ")
    print("="*60)
    
    cert_files = {
        "ROOT": "finance_pki/root/rootCA.crt",
        "INTERMEDIATE": "finance_pki/intermediate/intermediateCA.crt",
        "SERVICE": "finance_pki/certs/user_service/user_service.crt"
    }
    
    for name, path in cert_files.items():
        print_cert_details(path, name)
    
    result = verify_cert_chain(
        cert_files["SERVICE"],
        cert_files["INTERMEDIATE"],
        cert_files["ROOT"]
    )
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ ПРОВЕРКИ:", "УСПЕШНО" if result else "НЕ УДАЛОСЬ")
    print("="*60)
    
    sys.exit(0 if result else 1)