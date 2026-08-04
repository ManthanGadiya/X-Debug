import { AppShell, Box, Burger, Group, NavLink, Stack, Text } from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { NavLink as RouterNavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', index: '01', end: true },
  { to: '/projects', label: 'Projects', index: '02', end: false },
  { to: '/analysis', label: 'Analysis', index: '03', end: false },
  { to: '/runtime', label: 'Runtime', index: '04', end: false },
  { to: '/tests', label: 'Tests', index: '05', end: false },
  { to: '/reports', label: 'Reports', index: '06', end: false },
]

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure()

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="lg"
    >
      <AppShell.Header withBorder>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <LogoMark />
            <Text fw={600} size="lg" style={{ letterSpacing: '0.02em' }}>
              XDebug
            </Text>
            <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--xmono)' }} mt={4}>
              EXPLAINABLE DEBUGGING INSTRUMENT
            </Text>
          </Group>
          <Group gap={6}>
            <span className="xd-pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: '#1cc57f' }} />
            <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--xmono)' }}>
              READY
            </Text>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm" withBorder>
        <Stack gap={2}>
          {NAV_ITEMS.map((item) => (
            <RouterNavLink key={item.to} to={item.to} end={item.end} style={{ textDecoration: 'none' }}>
              {({ isActive }) => (
                <NavLink
                  component="span"
                  label={
                    <Group gap="xs">
                      <Text
                        size="xs"
                        c={isActive ? 'brand' : 'dimmed'}
                        style={{ fontFamily: 'var(--xmono)', minWidth: 20 }}
                      >
                        {item.index}
                      </Text>
                      <Text size="sm" fw={isActive ? 600 : 400}>
                        {item.label}
                      </Text>
                    </Group>
                  }
                  active={isActive}
                  variant="light"
                  style={{
                    borderRadius: 'var(--mantine-radius-md)',
                    marginBottom: 2,
                  }}
                />
              )}
            </RouterNavLink>
          ))}
        </Stack>
        <Box style={{ marginTop: 'auto' }}>
          <Text size="xs" c="dimmed" style={{ fontFamily: 'var(--xmono)' }} ta="center">
            XD-CONSOLE · v0.1
          </Text>
        </Box>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}

function LogoMark() {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <rect x="1" y="1" width="30" height="30" rx="8" stroke="#00b5dd" strokeWidth="1.5" fill="rgba(0,181,221,0.08)" />
      <path d="M8 20 L12 20 L14 12 L17 24 L20 14 L22 20 L24 20" stroke="#00b5dd" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
      <circle cx="24" cy="24" r="2.5" fill="#1cc57f" />
    </svg>
  )
}
