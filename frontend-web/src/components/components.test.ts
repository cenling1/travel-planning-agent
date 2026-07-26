import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const viewMocks = vi.hoisted(() => ({
  login: vi.fn(),
  push: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: viewMocks.push }),
  useRoute: () => ({ query: { redirect: '/documents' } }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    login: viewMocks.login,
    loginError: null,
    isLoginLoading: false,
  }),
}))

vi.mock('@/stores/system', () => ({
  useSystemStore: () => ({ health: { registration_enabled: false } }),
}))

import LoginView from '@/views/LoginView.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import ConfirmButton from '@/components/common/ConfirmButton.vue'

const ElFormStub = defineComponent({
  name: 'ElForm',
  setup(_props, { expose, slots }) {
    expose({ validate: async () => true })
    return () => h('form', slots.default?.())
  },
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  inheritAttrs: false,
  props: {
    modelValue: { type: String, default: '' },
    type: { type: String, default: 'text' },
    disabled: Boolean,
  },
  emits: ['update:modelValue', 'keydown'],
  setup(props, { attrs, emit, expose }) {
    expose({ focus: () => undefined })
    return () => {
      const nativeAttrs = { ...attrs }
      delete nativeAttrs.size
      delete nativeAttrs.resize
      delete nativeAttrs.showPassword
      return h(props.type === 'textarea' ? 'textarea' : 'input', {
        ...nativeAttrs,
        disabled: props.disabled,
        value: props.modelValue,
        onInput: (event: Event) => emit('update:modelValue', (event.target as HTMLInputElement).value),
        onKeydown: (event: KeyboardEvent) => emit('keydown', event),
      })
    }
  },
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  inheritAttrs: false,
  props: { disabled: Boolean, loading: Boolean },
  setup(props, { attrs, slots }) {
    return () => h('button', { ...attrs, disabled: props.disabled }, slots.default?.())
  },
})

const ElPopconfirmStub = defineComponent({
  name: 'ElPopconfirm',
  emits: ['confirm'],
  setup(_props, { emit, slots }) {
    return () => h('div', [
      slots.reference?.(),
      h('button', { class: 'test-confirm', onClick: () => emit('confirm') }, 'confirm'),
    ])
  },
})

const commonStubs = {
  ElForm: ElFormStub,
  ElFormItem: defineComponent({ setup: (_props, { slots }) => () => h('div', slots.default?.()) }),
  ElInput: ElInputStub,
  ElButton: ElButtonStub,
  ElAlert: true,
  ElLink: true,
}

describe('critical form components', () => {
  beforeEach(() => vi.clearAllMocks())

  it('submits login credentials and returns to the requested page', async () => {
    viewMocks.login.mockResolvedValue(true)
    const wrapper = mount(LoginView, { global: { stubs: commonStubs } })

    await wrapper.get('input[autocomplete="username"]').setValue('traveler')
    await wrapper.get('input[autocomplete="current-password"]').setValue('secret-password')
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(viewMocks.login).toHaveBeenCalledWith({ username: 'traveler', password: 'secret-password' })
    expect(viewMocks.push).toHaveBeenCalledWith('/documents')
  })

  it('trims and emits one chat message, then exposes the stop action', async () => {
    const wrapper = mount(ChatInput, {
      props: { isGenerating: false },
      global: { stubs: { ElInput: ElInputStub, ElButton: ElButtonStub } },
    })

    await wrapper.get('textarea').setValue('  Hangzhou weekend  ')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('send')).toEqual([['Hangzhou weekend']])

    await wrapper.setProps({ isGenerating: true })
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('emits a destructive action only after confirmation', async () => {
    const wrapper = mount(ConfirmButton, {
      props: { title: 'Delete', message: 'Delete this item?', type: 'danger' },
      slots: { default: 'Delete' },
      global: { stubs: { ElPopconfirm: ElPopconfirmStub, ElButton: ElButtonStub } },
    })

    expect(wrapper.emitted('confirm')).toBeUndefined()
    await wrapper.get('.test-confirm').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
