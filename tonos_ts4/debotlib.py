from tonos_ts4 import ts4
eq = ts4.eq

def load_debot(filename, nickname):
    global g_debot
    g_debot = ts4.BaseContract(filename, {}, nickname = nickname)
    g_debot.call_method('start', {}, is_debot = True)
    return g_debot

class Terminal(ts4.BaseContract):
    def __init__(self):
        addr = ts4.Address('-31:8796536366ee21852db56dccb60bc564598b618c865fc50c8b1ab740bba128e3')
        super(Terminal, self).__init__('common/TerminalImpl', {}, nickname = 'term', override_address = addr)

    def expect_print(self, txt):
        msg = ts4.pop_event()
        assert msg.is_event('Print', src = self.addr)
        e = self.decode_event(msg)
        ts4.verbose_(e.message)
        if txt is not None:
            assert eq(txt, e.message)

    def expect_input(self, txt):
        msg = ts4.pop_event()
        # print(msg)
        assert msg.is_event('Input', src = self.addr)
        e = self.decode_event(msg)
        ts4.verbose_(e.prompt)
        assert eq(txt, e.prompt)
        return e.answerId

    def expect_input2(self, txt, answer):
        answerId = self.expect_input(txt)
        self.send_input(answerId, answer)

    def send_input(self, answerId, txt):
        self.call_method('call_input', dict(
            addr = g_debot.addr,
            answerId = answerId,
            txt = txt,
        ))


class ConfirmInput(ts4.BaseContract):
    def __init__(self):
        addr = ts4.Address('-31:16653eaf34c921467120f2685d425ff963db5cbb5aa676a62a2e33bfc3f6828a')
        super(ConfirmInput, self).__init__('common/ConfirmInputImpl', {}, nickname = 'confirmInput', override_address = addr)

    def expect(self, prompt, answer):
        assert eq(prompt, self.call_getter('m_prompt'))
        self.call_method('reply', dict(answer = answer))

class AddressInput(ts4.BaseContract):
    def __init__(self):
        addr = ts4.Address('-31:d7ed1bd8e6230871116f4522e58df0a93c5520c56f4ade23ef3d8919a984653b')
        super(AddressInput, self).__init__('common/AddressInputImpl', {}, nickname = 'addrInp', override_address = addr)

    def expect_get(self, prompt):
        msg = ts4.pop_event()
        # print(msg)
        assert msg.is_event('Get', src = self.addr)
        e = self.decode_event(msg)
        ts4.verbose_(e.prompt)
        assert eq(prompt, e.prompt)
        return e.answerId

    def reply_get(self, answerId, addr):
        self.call_method('reply_get', dict(
            debot_addr = g_debot.addr,
            answerId = answerId,
            answer_addr = addr,
        ))


class DebotMenu(ts4.BaseContract):
    def __init__(self):
        addr = ts4.Address('-31:ac1a4d3ecea232e49783df4a23a81823cdca3205dc58cd20c4db259c25605b48')
        super(DebotMenu, self).__init__('common/MenuImpl', {}, nickname = 'menu', override_address = addr)

    def expect_menu(self, title):
        self.title = self.call_getter('m_title')
        assert eq(title, self.title)
        self.description = self.call_getter('m_description')
        self.items = self.call_getter('m_items', decode = True)
        
        print('MENU:', self.title)
        print('MENU:', self.description)
        for item in self.items:
            print('MENU:', item.__raw__)

    def select(self, title):
        print('Selecting:', title)
        for index, item in enumerate(self.items):
            if item.title == title:
                self.call_method('reply_select', dict(index = index))
                return
        assert False, "No '{}' in menu".format(title)


class DebotContext():
    def __init__(self):
        self.term           = Terminal()
        self.addrInp        = AddressInput()
        self.menu           = DebotMenu()
        self.confirmInput   = ConfirmInput()

        self.auto_dispatch  = False
        self._prints        = []
        self.expect_ec      = [0]

    def load_debot(self, filename, nickname):
        debot = load_debot(filename, nickname)
        if self.auto_dispatch:
            self.dispatch_messages()        
        return debot

    def dispatch_messages(self):
        while True:
            msg = ts4.peek_msg()
            # print(msg)
            if msg is None:
                break
            if msg.is_call():
                # verbose_('call')
                ts4.dispatch_one_message(expect_ec = self.expect_ec)
            else:
                break
        while True:
            event = ts4.peek_event()
            if event is None:
                break
            if event.is_event('Print', src = self.term.addr):
                ts4.pop_event()
                e = self.term.decode_event(event)
                ts4.verbose_(e.message)
                self._prints.append(e.message)
            else:
                break

    def set_keypair(self, keys):
        secret = keys[0][:64]
        pubkey = keys[1].replace('0x', '')
        ts4.core.set_debot_keypair(secret, pubkey)

    def expect_menu(self, title, select):
        if self.auto_dispatch: 
            self.dispatch_messages()
        self.menu.expect_menu(title)
        self.menu.select(select)
        if self.auto_dispatch: 
            self.dispatch_messages()

    def expect_address_input(self, title, reply):
        if self.auto_dispatch: 
            self.dispatch_messages()
        answerId = self.addrInp.expect_get(title)
        self.addrInp.reply_get(answerId, reply)
        if self.auto_dispatch: 
            self.dispatch_messages()

    def expect_input(self, txt, answer):
        if self.auto_dispatch: 
            self.dispatch_messages()
        self.term.expect_input2(txt, answer)
        if self.auto_dispatch: 
            self.dispatch_messages()

    def expect_confirmInput(self, txt, answer):
        if self.auto_dispatch: 
            self.dispatch_messages()
        self.confirmInput.expect(txt, answer)
        if self.auto_dispatch: 
            self.dispatch_messages()

    def expect_print(self, msg):
        while len(self._prints) > 0:
            t = self._prints.pop(0)
            if msg in t:
                return
        assert False, "msg = {}".format(msg)


