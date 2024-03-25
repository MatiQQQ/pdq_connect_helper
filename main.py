import json
import locale
import sys
from datetime import datetime
from time import sleep
import requests as req
from PyQt5.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton, QListWidget, \
    QFileDialog, QTextEdit
from babel.dates import format_datetime


class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.edit_btn = None
        self.save_btn = None
        self.api_key_input = None
        self.final_devices = []
        self.final_package = ''
        self.devices_list = []
        self.package_name_input = None
        self.load_file_btn = None
        self.get_data_btn = None
        self.deploy_btn = None
        self.api_data_display = None
        self.init_ui()


    def init_ui(self):
        self.resize(500, 600)

        layout = QVBoxLayout()

        self.setup_api_key_section(layout)
        self.load_file_btn = QPushButton('Load Devices List', self)
        self.load_file_btn.clicked.connect(self.load_file)
        layout.addWidget(self.load_file_btn)

        self.devices_list = QListWidget(self)
        layout.addWidget(self.devices_list)

        self.package_name_input = QLineEdit(self)
        self.package_name_input.setPlaceholderText("Enter Package Name")
        layout.addWidget(self.package_name_input)

        self.get_data_btn = QPushButton('Get Data', self)
        self.get_data_btn.clicked.connect(self.get_package_data)
        layout.addWidget(self.get_data_btn)

        self.api_data_display = QTextEdit(self)
        self.api_data_display.setReadOnly(True)
        layout.addWidget(self.api_data_display)

        self.deploy_btn = QPushButton('Deploy', self)
        self.deploy_btn.clicked.connect(self.deploy)
        layout.addWidget(self.deploy_btn)

        self.setLayout(layout)
        self.setWindowTitle('PDQ Connect Deployment Helper')

    def save_api_key(self) -> None:
        self.api_key_input.setReadOnly(True)
        self.save_btn.setEnabled(False)
        self.edit_btn.setEnabled(True)

    def edit_api_key(self) -> None:
        self.api_key_input.setReadOnly(False)
        self.save_btn.setEnabled(True)
        self.edit_btn.setEnabled(False)


    def setup_api_key_section(self, parent_layout: QVBoxLayout) -> None:
        api_key_layout = QHBoxLayout()
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setPlaceholderText("Enter API Key")
        api_key_layout.addWidget(self.api_key_input)

        self.save_btn = QPushButton('Save', self)
        self.save_btn.clicked.connect(self.save_api_key)
        api_key_layout.addWidget(self.save_btn)

        self.edit_btn = QPushButton('Edit', self)
        self.edit_btn.clicked.connect(self.edit_api_key)
        api_key_layout.addWidget(self.edit_btn)

        parent_layout.addLayout(api_key_layout)

    @staticmethod
    def parse_devices(file_path: str) -> list:
        with open(file_path, 'r') as f:
            return sorted(set([line.strip().upper() for line in f.readlines()]))

    def load_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Devices List")
        if file_name:
            parsed_devices = MyApp.parse_devices(f"{file_name}")
            pdq_devices = self.get_devices_from_pdq(parsed_devices)
            if len(pdq_devices) > 0:
                self.devices_list.addItems(pdq_devices)
            else:
                self.devices_list.addItems(['No Devices Found'])

    @staticmethod
    def generate_date_log():
        user_locale = locale.getlocale()[0]
        now = datetime.now()
        formatted_date = format_datetime(now, locale=user_locale)
        return f"[{formatted_date}]"

    def get_package_data(self):
        package_name = self.package_name_input.text()
        parsed_package_name = "%20".join(package_name.split(" "))
        try:
            package_response = self.create_request(
                url=f"https://app.pdq.com/v1/api/packages?pageSize=50&page=1&sort=nameDesc&filter%5Bname%5D=~{parsed_package_name}")
            package_data = package_response['data'][0]
            package_name_pdq = package_data['name']
            package_id_pdq = package_data['id']
            package_last_ver_pdq = package_data['latestPackageVersionId']
            package_dict = json.dumps(
                dict(package_name=package_name_pdq, package_id=package_id_pdq, package_last_ver=package_last_ver_pdq),
                indent=2)
            self.final_package = package_last_ver_pdq
            self.api_data_display.setText(f"{MyApp.generate_date_log()}\nAPI Data for package: \n{package_dict}")

        except req.exceptions.HTTPError as http_err:
            print(f'HTTP error occurred: {http_err}')
        except Exception as err:
            print(f'An error occurred: {err}')

    def deploy(self):
        if len(self.final_package) <= 0 or self.final_package == '':
            self.api_data_display.append(
                f"{MyApp.generate_date_log()}\nDeployment cannot be done because no package or no devices")
        else:
            print(f"{MyApp.generate_date_log()}\nPreparing Deployment...")
            parsed_devices = "".join(
                [f"{index + 1}: {device[0]} {device[1]}\n" for index, device in enumerate(self.final_devices)])
            url_list_of_devices = "".join([f"{device[1]}%2C" for device in self.final_devices]).removesuffix("%2C")
            final_url = f"https://app.pdq.com/v1/api/deployments?package={self.final_package}&targets={url_list_of_devices}"
            print(final_url)
            self.api_data_display.append(f"{MyApp.generate_date_log()}\nDeploying to listed devices...")
            self.api_data_display.append(parsed_devices)
            try:
                self.create_request(method='POST', url=final_url)
                self.api_data_display.append(f"{MyApp.generate_date_log()}\nRequest sent to PDQ")
            except req.exceptions.HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
            except Exception as err:
                print(f'An error occurred: {err}')

    def get_devices_from_pdq(self, list_of_devices: list) -> list:
        result_device_list = []
        for device in list_of_devices:
            try:
                get_device_req = self.create_request(
                    url=f'https://app.pdq.com/v1/api/devices?includes=networking%2Cprocessors&pageSize=50&page=1&sort=insertedAt&filter%5Bhostname%5D=~{device}')
                device_id = get_device_req['data'][0]['id']
                result_device_list.append(f"{device} ({device_id})")
                self.final_devices.append((device, device_id))
            except Exception as e:
                print('An error occurred j', e)
                continue
            sleep(0.5)
        return result_device_list

    def create_request(self, url: str = '', data: str = '', method: str = 'GET') -> dict | None:
        result_data = ''
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.api_key_input.text()}'
        }
        if method == 'POST':
            headers['accept'] = '*/*'

        if method == 'GET':
            try:
                response = req.get(url=url, headers=headers)
                response.raise_for_status()
                result_data = response.json()
            except req.exceptions.HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
            except Exception as err:
                print(f'An error occurred: {err}')
        elif method == 'POST':
            try:
                response = req.post(url=url, headers=headers, data=data)
                response.raise_for_status()
                result_data = dict(success=True)
            except req.exceptions.HTTPError as http_err:
                print(f'HTTP error occurred: {http_err}')
            except Exception as err:
                print(f'An error occurred: {err}')

        return result_data


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MyApp()
    ex.show()
    sys.exit(app.exec_())
