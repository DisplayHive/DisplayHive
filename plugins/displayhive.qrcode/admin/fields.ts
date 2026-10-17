/** The kinds of QR code and the values each one asks for — the same keys as backend/payload.py (TYPES). */

export type InputKind = 'text' | 'textarea' | 'email' | 'tel' | 'url' | 'number' | 'datetime-local' | 'select' | 'check'

export interface QrInput {
  /** The value's key (stored as `<name>__<key>`); `null` is the field's own value (`<name>`). */
  key: string | null
  label: string
  kind: InputKind
  placeholder?: string
  options?: Array<{ label: string; value: string }>
  hint?: string
}

export interface QrType {
  id: string
  label: string
  inputs: QrInput[]
}

const text = (key: string, label: string, placeholder = ''): QrInput => ({ key, label, kind: 'text', placeholder })

export const QR_TYPES: QrType[] = [
  { id: 'url', label: 'Link / website', inputs: [{ key: null, label: 'Address', kind: 'url', placeholder: 'https://example.com' }] },
  { id: 'text', label: 'Plain text', inputs: [{ key: null, label: 'Text', kind: 'textarea', placeholder: 'Any text' }] },
  {
    id: 'vcard',
    label: 'Contact (vCard / MeCard)',
    inputs: [
      { key: 'vc_format', label: 'Format', kind: 'select', options: [{ label: 'vCard (all phones)', value: 'vcard' }, { label: 'MeCard (compact)', value: 'mecard' }] },
      text('vc_first', 'First name'), text('vc_last', 'Last name'), text('vc_org', 'Organisation'), text('vc_title', 'Job title'),
      { key: 'vc_phone', label: 'Phone', kind: 'tel' }, { key: 'vc_mobile', label: 'Mobile', kind: 'tel' },
      { key: 'vc_email', label: 'E-mail', kind: 'email' }, { key: 'vc_web', label: 'Website', kind: 'url' },
      text('vc_street', 'Street'), text('vc_zip', 'Postcode'), text('vc_city', 'City'), text('vc_country', 'Country'),
      { key: 'vc_note', label: 'Note', kind: 'textarea' },
    ],
  },
  {
    id: 'wifi',
    label: 'Wi-Fi',
    inputs: [
      text('wifi_ssid', 'Network name (SSID)'),
      { key: 'wifi_password', label: 'Password', kind: 'text' },
      { key: 'wifi_security', label: 'Security', kind: 'select', options: [{ label: 'WPA / WPA2 / WPA3', value: 'WPA' }, { label: 'WEP', value: 'WEP' }, { label: 'None (open)', value: 'nopass' }] },
      { key: 'wifi_hidden', label: 'Hidden network', kind: 'check' },
    ],
  },
  {
    id: 'email',
    label: 'E-mail',
    inputs: [{ key: 'mail_to', label: 'To', kind: 'email' }, text('mail_subject', 'Subject'), { key: 'mail_body', label: 'Message', kind: 'textarea' }],
  },
  { id: 'sms', label: 'SMS', inputs: [{ key: 'sms_number', label: 'Number', kind: 'tel' }, { key: 'sms_message', label: 'Message', kind: 'textarea' }] },
  { id: 'phone', label: 'Phone number', inputs: [{ key: 'tel_number', label: 'Number', kind: 'tel' }] },
  {
    id: 'geo',
    label: 'Map position',
    inputs: [text('geo_lat', 'Latitude', '52.5200'), text('geo_lon', 'Longitude', '13.4050')],
  },
  {
    id: 'event',
    label: 'Calendar event',
    inputs: [
      text('ev_title', 'Title'),
      { key: 'ev_start', label: 'Start', kind: 'datetime-local' }, { key: 'ev_end', label: 'End', kind: 'datetime-local' },
      text('ev_location', 'Location'), { key: 'ev_description', label: 'Description', kind: 'textarea' },
    ],
  },
  {
    id: 'sepa',
    label: 'SEPA payment (GiroCode)',
    inputs: [
      text('pay_name', 'Recipient'), text('pay_iban', 'IBAN', 'DE89 3704 0044 0532 0130 00'), text('pay_bic', 'BIC (optional)'),
      { key: 'pay_amount', label: 'Amount in EUR (optional)', kind: 'text', placeholder: '12.50' },
      text('pay_reference', 'Purpose'),
    ],
  },
]

export const QR_TYPE_OPTIONS = QR_TYPES.map((t) => ({ label: t.label, value: t.id }))
export const qrType = (id: string): QrType => QR_TYPES.find((t) => t.id === id) ?? QR_TYPES[0]!

/** Looks: stored as `<name>__<key>`. */
export const QR_LOOKS = {
  size: 'size', fg: 'fg', bg: 'bg', ec: 'ec', border: 'border',
} as const

export const EC_OPTIONS = [
  { label: 'Low (7 %) — smallest code', value: 'l' },
  { label: 'Medium (15 %)', value: 'm' },
  { label: 'Quartile (25 %)', value: 'q' },
  { label: 'High (30 %) — most robust', value: 'h' },
]
