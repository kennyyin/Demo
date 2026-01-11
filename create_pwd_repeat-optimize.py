"""
凯迪仕DMS系统 - UI自动化测试脚本（优化版）
功能：登录 + 门锁详情页 + 新增授权操作（支持重复执行）
优化：提高选择安装师傅的速度
作者：自动化测试
日期：2026
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import ddddocr
import base64
import time
import re


class CaptchaOCR:
    """验证码识别类"""

    def __init__(self):
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        print("✅ OCR识别器初始化完成")

    def recognize_base64(self, base64_str):
        """识别Base64编码的验证码"""
        try:
            if ',' in base64_str:
                base64_str = base64_str.split(',')[1]

            image_bytes = base64.b64decode(base64_str)
            result = self.ocr.classification(image_bytes)

            print(f"✅ 验证码识别结果: {result}")
            return result

        except Exception as e:
            print(f"❌ 验证码识别失败: {str(e)}")
            return None


class KaadasAutomation:
    """凯迪仕DMS系统自动化测试类"""

    def __init__(self, headless=False):
        """
        初始化
        :param headless: 是否无头模式运行
        """
        # 目标页面URL（打开后会自动跳转到登录页）
        self.target_url = "https://dms.kaadas.com/#/deviceList/detail/doorLockDetail/W5575A2401230AA1011195"
        self.login_url = "https://dms.kaadas.com/#/login"

        self.driver = None
        self.wait = None
        self.headless = headless
        self.ocr = CaptchaOCR()

    def setup_driver(self):
        """配置并启动Chrome浏览器"""
        chrome_options = Options()

        if self.headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # 防止被检测为自动化脚本
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 15)

        print("✅ 浏览器启动成功")

    def open_target_page(self):
        """
        打开目标页面（门锁详情页）
        系统会自动跳转到登录页面
        """
        print(f"\n{'=' * 60}")
        print("🌐 打开目标页面")
        print(f"{'=' * 60}")

        self.driver.get(self.target_url)
        print(f"✅ 已打开: {self.target_url}")
        time.sleep(3)

        # 检查是否跳转到登录页
        current_url = self.driver.current_url
        print(f"📍 当前URL: {current_url}")

        if "login" in current_url.lower():
            print("✅ 已跳转到登录页面，需要登录")
            return True
        else:
            print("✅ 已登录状态，无需重新登录")
            return False

    def analyze_input_fields(self):
        """分析页面上的所有输入框，精确定位"""
        print("\n🔍 分析页面输入框...")

        all_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input.el-input__inner")

        if not all_inputs:
            all_inputs = self.driver.find_elements(By.TAG_NAME, "input")

        print(f"   找到 {len(all_inputs)} 个输入框")

        username_input = None
        password_input = None
        captcha_input = None

        for i, inp in enumerate(all_inputs):
            try:
                input_type = inp.get_attribute('type') or ''
                placeholder = inp.get_attribute('placeholder') or ''
                is_displayed = inp.is_displayed()

                print(f"   输入框{i + 1}: type='{input_type}', placeholder='{placeholder}', visible={is_displayed}")

                if not is_displayed:
                    continue

                # 密码框
                if input_type == 'password':
                    password_input = inp
                    print(f"   ✅ 密码框: 输入框{i + 1}")

                # 用户名框或验证码框
                elif input_type == 'text' or input_type == '':
                    if '账号' in placeholder or '用户' in placeholder:
                        username_input = inp
                        print(f"   ✅ 用户名框: 输入框{i + 1}")
                    elif '验证码' in placeholder or '码' in placeholder:
                        captcha_input = inp
                        print(f"   ✅ 验证码框: 输入框{i + 1}")
                    elif username_input is None and password_input is None:
                        username_input = inp
                        print(f"   ✅ 用户名框(推断): 输入框{i + 1}")

            except Exception as e:
                continue

        # 如果还没找到验证码框，取最后一个非密码框
        if captcha_input is None:
            visible_inputs = [inp for inp in all_inputs
                              if inp.is_displayed() and inp.get_attribute('type') != 'password']
            if len(visible_inputs) >= 3:
                captcha_input = visible_inputs[-1]
                print(f"   ✅ 验证码框(推断): 最后一个可见输入框")

        return username_input, password_input, captcha_input

    def get_captcha_code(self):
        """获取并识别验证码"""
        try:
            print("\n🔄 获取验证码...")

            captcha_img = None
            locators = [
                (By.XPATH, "//img[contains(@src,'data:image')]"),
                (By.XPATH, "//img[contains(@src,'base64')]"),
                (By.CSS_SELECTOR, "img[src^='data:image']"),
            ]

            for locator in locators:
                try:
                    elements = self.driver.find_elements(*locator)
                    for elem in elements:
                        src = elem.get_attribute('src') or ''
                        if 'base64' in src and elem.is_displayed():
                            captcha_img = elem
                            print(f"   ✅ 找到验证码图片")
                            break
                    if captcha_img:
                        break
                except:
                    continue

            if not captcha_img:
                print("   ❌ 未找到验证码图片")
                return None

            captcha_src = captcha_img.get_attribute('src')
            captcha_code = self.ocr.recognize_base64(captcha_src)

            if captcha_code:
                captcha_code = re.sub(r'[^a-zA-Z0-9]', '', captcha_code)
                return captcha_code

            return None

        except Exception as e:
            print(f"   ❌ 获取验证码出错: {str(e)}")
            return None

    def click_captcha_to_refresh(self):
        """点击验证码图片刷新"""
        try:
            captcha_img = self.driver.find_element(By.XPATH, "//img[contains(@src,'data:image')]")
            captcha_img.click()
            time.sleep(1)
            print("   🔄 验证码已刷新")
        except:
            pass

    def login(self, username, password, max_attempts=3):
        """
        执行登录操作
        :param username: 用户名
        :param password: 密码
        :param max_attempts: 最大尝试次数
        :return: 是否登录成功
        """
        for attempt in range(max_attempts):
            try:
                print(f"\n{'=' * 60}")
                print(f"🚀 第 {attempt + 1}/{max_attempts} 次登录尝试")
                print(f"{'=' * 60}")

                if attempt > 0:
                    self.click_captcha_to_refresh()
                    time.sleep(1)

                # 1. 分析并定位所有输入框
                username_input, password_input, captcha_input = self.analyze_input_fields()

                if not all([username_input, password_input, captcha_input]):
                    print("❌ 无法定位所有输入框")
                    self.driver.refresh()
                    time.sleep(2)
                    continue

                # 2. 获取验证码
                captcha_code = self.get_captcha_code()

                if not captcha_code:
                    print("❌ 无法识别验证码，刷新重试...")
                    self.click_captcha_to_refresh()
                    continue

                # 3. 清空并填写表单
                username_input.clear()
                password_input.clear()
                captcha_input.clear()
                time.sleep(0.3)

                # 输入用户名
                username_input.click()
                time.sleep(0.2)
                username_input.send_keys(username)
                print(f"✅ 已输入用户名: {username}")

                # 输入密码
                password_input.click()
                time.sleep(0.2)
                password_input.send_keys(password)
                print(f"✅ 已输入密码: {'*' * len(password)}")

                # 输入验证码
                captcha_input.click()
                time.sleep(0.2)
                captcha_input.send_keys(captcha_code)
                print(f"✅ 已输入验证码: {captcha_code}")

                time.sleep(0.5)

                # 4. 验证输入是否正确
                actual_captcha = captcha_input.get_attribute('value')
                if actual_captcha != captcha_code:
                    print("⚠️ 验证码输入异常，重试...")
                    self.driver.refresh()
                    time.sleep(2)
                    continue

                # 5. 点击登录按钮
                login_button = None
                button_locators = [
                    (By.XPATH, "//button[contains(.,'登录')]"),
                    (By.XPATH, "//button[contains(.,'登 录')]"),
                    (By.XPATH, "//button[.//span[contains(text(),'登')]]"),
                    (By.CSS_SELECTOR, "button.el-button--primary"),
                ]

                for locator in button_locators:
                    try:
                        login_button = self.driver.find_element(*locator)
                        if login_button and login_button.is_displayed():
                            break
                    except:
                        continue

                if login_button:
                    login_button.click()
                    print("✅ 已点击登录按钮")
                else:
                    print("❌ 未找到登录按钮")
                    continue

                # 6. 验证登录结果
                time.sleep(3)

                current_url = self.driver.current_url
                print(f"\n📍 当前URL: {current_url}")

                if "login" not in current_url.lower():
                    print("\n" + "🎉" * 20)
                    print("       登录成功！")
                    print("🎉" * 20)
                    return True

                # 检查错误提示
                try:
                    error_element = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(@class,'el-message') or contains(@class,'error')]"
                    )
                    if error_element.is_displayed():
                        print(f"⚠️ 提示信息: {error_element.text}")
                except:
                    pass

            except Exception as e:
                print(f"❌ 登录过程出错: {str(e)}")
                self.take_screenshot(f"login_error_{attempt + 1}.png")
                self.driver.refresh()
                time.sleep(2)

        print("\n💔 登录失败，已达最大尝试次数")
        return False

    def wait_for_page_load(self):
        """等待页面加载完成"""
        print("\n⏳ 等待页面加载...")
        time.sleep(3)

        # 等待页面主要元素出现
        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'授权信息')]"))
            )
            print("✅ 页面加载完成")
        except:
            print("⚠️ 继续等待...")
            time.sleep(2)

    def click_authorization_tab(self):
        """点击授权信息标签"""
        print(f"\n{'=' * 60}")
        print("🏷️ 步骤1: 点击【授权信息】标签")
        print(f"{'=' * 60}")

        try:
            tab_locators = [
                (By.XPATH, "//div[contains(@class,'el-tabs__item') and contains(text(),'授权信息')]"),
                (By.XPATH, "//*[contains(@class,'el-tabs__item')][contains(.,'授权信息')]"),
                (By.XPATH, "//div[@role='tab' and contains(text(),'授权信息')]"),
                (By.XPATH, "//*[text()='授权信息']"),
                (By.XPATH, "//span[text()='授权信息']"),
                (By.XPATH, "//*[contains(text(),'授权信息')]"),
            ]

            tab_element = None
            for locator in tab_locators:
                try:
                    tab_element = self.wait.until(
                        EC.element_to_be_clickable(locator)
                    )
                    if tab_element:
                        print(f"   找到标签元素: {locator}")
                        break
                except:
                    continue

            if tab_element:
                # 滚动到元素可见
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab_element)
                time.sleep(0.5)
                tab_element.click()
                print("✅ 已点击【授权信息】标签")
                time.sleep(2)
                return True
            else:
                print("❌ 未找到【授权信息】标签")
                self.take_screenshot("tab_not_found.png")
                return False

        except Exception as e:
            print(f"❌ 点击授权信息标签失败: {str(e)}")
            return False

    def click_add_authorization_button(self):
        """点击新增授权按钮"""
        print(f"\n{'=' * 60}")
        print("➕ 步骤2: 点击【新增授权】按钮")
        print(f"{'=' * 60}")

        try:
            button_locators = [
                (By.XPATH, "//button[contains(.,'新增授权')]"),
                (By.XPATH, "//button[.//span[contains(text(),'新增授权')]]"),
                (By.XPATH, "//span[contains(text(),'新增授权')]/parent::button"),
                (By.XPATH, "//*[contains(@class,'el-button') and contains(.,'新增授权')]"),
                (By.XPATH, "//button[contains(@class,'el-button--primary')][contains(.,'新增')]"),
            ]

            add_button = None
            for locator in button_locators:
                try:
                    add_button = self.wait.until(
                        EC.element_to_be_clickable(locator)
                    )
                    if add_button:
                        print(f"   找到按钮元素: {locator}")
                        break
                except:
                    continue

            if add_button:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_button)
                time.sleep(0.5)
                add_button.click()
                print("✅ 已点击【新增授权】按钮")
                time.sleep(2)
                return True
            else:
                print("❌ 未找到【新增授权】按钮")
                self.take_screenshot("button_not_found.png")
                return False

        except Exception as e:
            print(f"❌ 点击新增授权按钮失败: {str(e)}")
            return False

    def select_dropdown_by_label(self, label_text, option_text):
        """
        通过标签文本定位下拉框并选择选项
        :param label_text: 标签文本
        :param option_text: 要选择的选项
        """
        try:
            print(f"\n   📌 {label_text} -> 选择【{option_text}】")

            # 定位包含标签的表单项
            form_item = None
            form_item_locators = [
                f"//label[contains(text(),'{label_text}')]/ancestor::div[contains(@class,'el-form-item')]",
                f"//*[contains(text(),'{label_text}')]/ancestor::div[contains(@class,'el-form-item')]",
                f"//div[contains(@class,'el-form-item')][.//label[contains(text(),'{label_text}')]]",
            ]

            for xpath in form_item_locators:
                try:
                    form_item = self.driver.find_element(By.XPATH, xpath)
                    if form_item:
                        break
                except:
                    continue

            # 点击下拉框
            if form_item:
                try:
                    select_input = form_item.find_element(By.CSS_SELECTOR, ".el-select input.el-input__inner")
                    select_input.click()
                except:
                    try:
                        select_div = form_item.find_element(By.CSS_SELECTOR, ".el-select")
                        select_div.click()
                    except:
                        form_item.click()
            else:
                # 备选方案
                dropdown = self.driver.find_element(
                    By.XPATH,
                    f"//*[contains(text(),'{label_text}')]/following::div[contains(@class,'el-select')][1]"
                )
                dropdown.click()

            time.sleep(0.5)  # 减少等待时间

            # 选择选项
            option_locators = [
                f"//li[contains(@class,'el-select-dropdown__item')][contains(.,'{option_text}')]",
                f"//div[contains(@class,'el-select-dropdown')]//li[contains(.,'{option_text}')]",
                f"//ul[contains(@class,'el-select-dropdown__list')]//li[contains(.,'{option_text}')]",
                f"//span[contains(text(),'{option_text}')]/ancestor::li",
            ]

            for xpath in option_locators:
                try:
                    options = self.driver.find_elements(By.XPATH, xpath)
                    for opt in options:
                        if opt.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opt)
                            time.sleep(0.2)  # 减少等待时间
                            opt.click()
                            print(f"   ✅ 已选择【{option_text}】")
                            time.sleep(0.3)  # 减少等待时间
                            return True
                except:
                    continue

            print(f"   ❌ 未找到选项【{option_text}】")
            return False

        except Exception as e:
            print(f"   ❌ 选择 {label_text} 失败: {str(e)}")
            return False

    def select_installer(self, installer_name):
        """
        选择安装师傅（优化版 - 更快的查找和选择）
        :param installer_name: 安装师傅名称
        """
        try:
            print(f"\n   📌 选择安装师傅 -> 【{installer_name}】")
            start_time = time.time()

            # 定位安装师傅下拉框
            installer_locators = [
                "//label[contains(text(),'安装师傅')]/following-sibling::div//input",
                "//label[contains(text(),'选择安装师傅')]/following-sibling::div//input",
                "//*[contains(text(),'安装师傅')]/following::div[contains(@class,'el-select')][1]//input",
                "//input[@placeholder='请选择安装师傅']",
                "//input[contains(@placeholder,'安装师傅')]",
                "//input[contains(@placeholder,'选择')]",
            ]

            dropdown = None
            for xpath in installer_locators:
                try:
                    dropdown = self.driver.find_element(By.XPATH, xpath)
                    if dropdown and dropdown.is_displayed():
                        print(f"   找到下拉框: {xpath}")
                        break
                except:
                    continue

            if not dropdown:
                # 尝试点击对话框中的第三个下拉框
                all_selects = self.driver.find_elements(By.CSS_SELECTOR, ".el-dialog .el-select")
                print(f"   找到 {len(all_selects)} 个下拉框")
                if len(all_selects) >= 3:
                    dropdown = all_selects[2]

            if dropdown:
                # 滚动到视图并点击
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropdown)
                time.sleep(0.2)  # 减少等待时间
                dropdown.click()
                time.sleep(0.3)  # 减少等待时间
            else:
                print("   ❌ 未找到安装师傅下拉框")
                return False

            # 等待下拉列表加载
            time.sleep(0.2)
            option_found = False

            # 获取下拉列表容器
            dropdown_wrapper = None
            try:
                dropdown_wrapper = self.driver.find_element(
                    By.XPATH,
                    "//div[contains(@class,'el-select-dropdown') and not(contains(@style,'display: none'))]"
                )
            except:
                pass

            # 优化策略1: 先尝试直接查找选项，不需要滚动
            try:
                option = self.driver.find_element(
                    By.XPATH,
                    f"//li[contains(@class,'el-select-dropdown__item')][contains(.,'{installer_name}')]"
                )
                if option.is_displayed():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                    time.sleep(0.1)  # 减少等待时间
                    option.click()
                    print(f"   ✅ 已选择【{installer_name}】(直接查找)")
                    option_found = True
            except:
                pass

            # 优化策略2: 如果直接查找失败，尝试JavaScript查找
            if not option_found:
                try:
                    js_code = f"""
                    var items = document.querySelectorAll('.el-select-dropdown__item');
                    for (var i = 0; i < items.length; i++) {{
                        if (items[i].textContent.includes('{installer_name}')) {{
                            items[i].scrollIntoView({{block: 'center'}});
                            items[i].click();
                            return true;
                        }}
                    }}
                    return false;
                    """
                    result = self.driver.execute_script(js_code)
                    if result:
                        print(f"   ✅ 已选择【{installer_name}】(JavaScript查找)")
                        option_found = True
                except:
                    pass

            # 优化策略3: 智能滚动查找（减少滚动次数，增加滚动步长）
            if not option_found and dropdown_wrapper:
                max_scroll = 8  # 减少滚动次数
                scroll_step = 120  # 增加滚动步长

                for scroll_count in range(max_scroll):
                    try:
                        option = self.driver.find_element(
                            By.XPATH,
                            f"//li[contains(@class,'el-select-dropdown__item')][contains(.,'{installer_name}')]"
                        )
                        if option.is_displayed():
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", option)
                            time.sleep(0.1)  # 减少等待时间
                            option.click()
                            print(f"   ✅ 已选择【{installer_name}】(滚动查找)")
                            option_found = True
                            break
                    except:
                        pass

                    # 向下滚动列表（更大的步长）
                    if dropdown_wrapper:
                        try:
                            scroll_element = dropdown_wrapper.find_element(By.CSS_SELECTOR, ".el-select-dropdown__wrap")
                            self.driver.execute_script(f"arguments[0].scrollTop += {scroll_step};", scroll_element)
                            time.sleep(0.1)  # 减少等待时间
                        except:
                            break

            # 优化策略4: 最后尝试遍历所有选项
            if not option_found:
                all_options = self.driver.find_elements(
                    By.XPATH,
                    "//li[contains(@class,'el-select-dropdown__item')]"
                )
                for opt in all_options:
                    try:
                        if installer_name in opt.text:
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", opt)
                            time.sleep(0.1)  # 减少等待时间
                            opt.click()
                            print(f"   ✅ 已选择【{installer_name}】(遍历查找)")
                            option_found = True
                            break
                    except:
                        continue

            # 计算执行时间
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"   ⏱️ 选择安装师傅耗时: {execution_time:.2f}秒")

            time.sleep(0.2)  # 减少等待时间
            return option_found

        except Exception as e:
            print(f"   ❌ 选择安装师傅失败: {str(e)}")
            return False

    def click_confirm_button(self):
        """点击确定按钮（优化版）"""
        try:
            print(f"\n   📌 点击【确定】按钮")

            # 等待一下，确保表单数据填写完成
            time.sleep(0.5)  # 减少等待时间

            confirm_locators = [
                "//div[contains(@class,'el-dialog')]//button[contains(.,'确定')]",
                "//div[contains(@class,'el-dialog')]//button[contains(.,'确 定')]",
                "//div[contains(@class,'el-dialog__footer')]//button[contains(@class,'el-button--primary')]",
                "//span[text()='确定']/parent::button",
                "//span[text()='确 定']/parent::button",
                "//div[@class='el-dialog__footer']//button[2]",  # 通常确定是第二个按钮
            ]

            confirm_button = None
            for xpath in confirm_locators:
                try:
                    buttons = self.driver.find_elements(By.XPATH, xpath)
                    for btn in buttons:
                        if btn.is_displayed() and btn.is_enabled():
                            confirm_button = btn
                            print(f"   找到按钮: {xpath}")
                            break
                    if confirm_button:
                        break
                except:
                    continue

            if not confirm_button:
                print("   ❌ 未找到确定按钮")
                return False

            # ========== 多种点击方式尝试 ==========
            click_success = False

            # 方式1：滚动到元素并常规点击
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_button)
                time.sleep(0.3)  # 减少等待时间
                confirm_button.click()
                click_success = True
                print("   ✅ 方式1(常规点击)成功")
            except Exception as e:
                print(f"   ⚠️ 方式1失败: {e}")

            # 方式2：JavaScript点击
            if not click_success:
                try:
                    self.driver.execute_script("arguments[0].click();", confirm_button)
                    click_success = True
                    print("   ✅ 方式2(JavaScript点击)成功")
                except Exception as e:
                    print(f"   ⚠️ 方式2失败: {e}")

            # 方式3：ActionChains点击
            if not click_success:
                try:
                    actions = ActionChains(self.driver)
                    actions.move_to_element(confirm_button).click().perform()
                    click_success = True
                    print("   ✅ 方式3(ActionChains点击)成功")
                except Exception as e:
                    print(f"   ⚠️ 方式3失败: {e}")

            if click_success:
                time.sleep(0.5)  # 减少等待时间
                print("   ✅ 已点击确定按钮")
                return True
            else:
                print("   ❌ 所有点击方式均失败")
                return False

        except Exception as e:
            print(f"   ❌ 点击确定按钮失败: {str(e)}")
            return False

    def perform_authorization_operation(self):
        """
        执行完整的授权操作
        返回: 操作是否成功
        """
        try:
            print(f"\n{'=' * 60}")
            print("🔄 开始执行授权操作")
            print(f"{'=' * 60}")

            # 1. 点击"授权信息"标签
            if not self.click_authorization_tab():
                print("❌ 无法点击授权信息标签")
                return False

            # 2. 点击"新增授权"按钮
            if not self.click_add_authorization_button():
                print("❌ 无法点击新增授权按钮")
                return False

            # 3. 填写授权表单
            if not self.fill_authorization_form():
                print("❌ 填写授权表单失败")
                return False

            print("\n" + "🎉" * 20)
            print("       授权操作完成！")
            print("🎉" * 20)

            return True

        except Exception as e:
            print(f"❌ 授权操作执行失败: {str(e)}")
            self.take_screenshot("authorization_operation_error.png")
            return False

    def fill_authorization_form(self):
        """填写新增授权表单"""
        print(f"\n{'=' * 60}")
        print("📝 步骤3: 填写新增授权表单")
        print(f"{'=' * 60}")

        try:
            # 等待对话框出现
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".el-dialog__wrapper"))
            )
            time.sleep(0.5)  # 减少等待时间
            print("✅ 授权对话框已打开")

            # ========== 第一步：授权类型选择"密码" ==========
            print("\n" + "-" * 40)
            print("第一步：授权类型")
            print("-" * 40)
            self.select_dropdown_by_label("授权类型", "密码")
            time.sleep(0.5)  # 减少等待时间

            # ========== 第二步：被授权人角色选择"安装师傅" ==========
            print("\n" + "-" * 40)
            print("第二步：被授权人角色")
            print("-" * 40)
            self.select_dropdown_by_label("被授权人角色", "安装师傅")
            time.sleep(0.5)  # 减少等待时间

            # ========== 第三步：选择安装师傅 ==========
            print("\n" + "-" * 40)
            print("第三步：选择安装师傅")
            print("-" * 40)
            self.select_installer("尹传清(18566227407)")
            time.sleep(0.5)  # 减少等待时间

            # ========== 第四步：授权时长选择"一个月" ==========
            print("\n" + "-" * 40)
            print("第四步：授权时长")
            print("-" * 40)
            self.select_dropdown_by_label("授权时长", "一个月")
            time.sleep(0.5)  # 减少等待时间

            # ========== 第五步：点击确定按钮 ==========
            print("\n" + "-" * 40)
            print("第五步：确认提交")
            print("-" * 40)
            self.click_confirm_button()

            return True

        except Exception as e:
            print(f"❌ 填写授权表单失败: {str(e)}")
            self.take_screenshot("authorization_error.png")
            return False

    def take_screenshot(self, filename="screenshot.png"):
        """截图保存"""
        try:
            self.driver.save_screenshot(filename)
            print(f"📸 截图已保存: {filename}")
        except Exception as e:
            print(f"⚠️ 截图失败: {e}")

    def close(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            print("\n✅ 浏览器已关闭")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("      凯迪仕DMS系统 - UI自动化测试（优化版）")
    print("=" * 60)

    # ========== 配置登录信息 ==========
    USERNAME = "18566227407"
    PASSWORD = "zh@8888"

    print(f"\n📋 测试配置:")
    print(f"   用户名: {USERNAME}")
    print(f"   密码: {'*' * len(PASSWORD)}")
    print(f"   目标: 门锁授权操作（支持重复执行）")
    print(f"   优化: 提高选择安装师傅的速度")

    # ========== 执行自动化测试 ==========
    bot = KaadasAutomation(headless=False)

    try:
        # 1. 启动浏览器
        bot.setup_driver()

        # 2. 打开目标页面（会自动跳转到登录页）
        need_login = bot.open_target_page()

        # 3. 如果需要登录，执行登录操作
        if need_login:
            login_success = bot.login(USERNAME, PASSWORD, max_attempts=3)

            if not login_success:
                print("\n❌ 登录失败，终止测试")
                bot.take_screenshot("login_failed.png")
                return

        # 4. 等待页面加载（登录成功后会自动跳转到目标页面）
        bot.wait_for_page_load()

        # 5. 重复执行授权操作
        repeat_count = 3  # 设置重复执行次数
        success_count = 0

        for i in range(repeat_count):
            print(f"\n{'=' * 60}")
            print(f"🔁 第 {i + 1}/{repeat_count} 次授权操作")
            print(f"{'=' * 60}")

            # 执行授权操作
            if bot.perform_authorization_operation():
                success_count += 1
                print(f"✅ 第 {i + 1} 次授权操作成功")

                # 操作间隔，避免过于频繁
                if i < repeat_count - 1:  # 如果不是最后一次
                    print(f"\n⏳ 等待3秒后执行下一次操作...")  # 减少等待时间
                    time.sleep(3)  # 减少等待时间
            else:
                print(f"❌ 第 {i + 1} 次授权操作失败")
                # 截图保存失败状态
                bot.take_screenshot(f"authorization_failed_{i + 1}.png")

                # 询问是否继续下一次尝试
                if i < repeat_count - 1:
                    print("继续下一次尝试...")

        # 6. 统计结果
        print(f"\n{'=' * 60}")
        print("📊 操作统计")
        print(f"{'=' * 60}")
        print(f"   总执行次数: {repeat_count}")
        print(f"   成功次数: {success_count}")
        print(f"   失败次数: {repeat_count - success_count}")
        print(f"   成功率: {(success_count / repeat_count) * 100:.1f}%")

        # 7. 截图保存最终结果
        bot.take_screenshot("test_final_result.png")

        print("\n" + "=" * 60)
        print("✨ UI自动化测试全部完成！")
        print("=" * 60)

        # 保持浏览器打开，方便查看结果
        time.sleep(5)

    except Exception as e:
        print(f"\n❌ 测试执行错误: {str(e)}")
        import traceback
        traceback.print_exc()
        bot.take_screenshot("test_error.png")

    finally:
        bot.close()


if __name__ == "__main__":
    main()
