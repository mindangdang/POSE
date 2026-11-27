import { expect, test } from '@playwright/test';

const searchResult = {
  search_id: 'browser-search',
  status: 'completed',
  intent: {
    objective: 'Find a quiet study cafe',
    rewritten_query: 'quiet study cafe',
    criteria: [
      {
        id: 'quiet-criterion',
        attribute: 'noise_level',
        operator: 'semantic_match',
        value: 'quiet',
        weight: 0.85,
        confidence: 1,
        is_hard_constraint: false,
        source: 'explicit',
      },
    ],
    exclusions: [],
    unresolved_information: [],
    clarification_required: false,
  },
  preferences_used: [],
  verified_results: [
    {
      document: {
        document_id: 'quiet-cafe',
        canonical_url: 'https://example.org/quiet-cafe',
        title: 'Quiet study cafe',
        snippet: 'Quiet seating and power outlets.',
        content: 'Quiet seating and power outlets.',
        source: 'fixture',
        metadata: {},
      },
      rank: 1,
      score: 0.82,
      verified: true,
      reason: 'The page supports the requested features.',
      satisfied_criteria: [],
      uncertain_criteria: [],
      evaluations: [],
    },
  ],
  unverified_results: [],
  excluded_result_count: 0,
  errors: [],
};

test('search results, personalization opt-out, and feedback work', async ({ page }) => {
  const submitted: Array<Record<string, unknown>> = [];
  let feedback: Record<string, unknown> | undefined;
  let preferences: Array<Record<string, unknown>> = [];
  await page.route('**/api/v2/search', async (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    submitted.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({ json: { search_id: `browser-search-${submitted.length}`, status: 'queued' } });
  });
  await page.route('**/api/v2/search/*', (route) => {
    const searchId = new URL(route.request().url()).pathname.split('/').at(-1) ?? '';
    return route.fulfill({ json: { ...searchResult, search_id: searchId } });
  });
  await page.route('**/api/v2/preferences**', async (route) => {
    const method = route.request().method();
    if (method === 'POST') {
      const created = { ...route.request().postDataJSON() as Record<string, unknown>, id: 'pref-1' };
      preferences = [created];
      return route.fulfill({ status: 201, json: created });
    }
    if (method === 'PATCH') {
      const changes = route.request().postDataJSON() as Record<string, unknown>;
      preferences = preferences.map((item) => ({ ...item, ...changes }));
      return route.fulfill({ json: preferences[0] });
    }
    if (method === 'DELETE') {
      preferences = [];
      return route.fulfill({ status: 204, body: '' });
    }
    return route.fulfill({ json: preferences });
  });
  await page.route('**/api/v2/feedback', async (route) => {
    feedback = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({ json: { status: 'success', updated_preferences: 0 } });
  });

  await page.goto('/test-harness.html');
  await page.getByLabel('검색어').fill('quiet study cafe');
  await page.getByRole('checkbox', { name: '내 선호 반영' }).uncheck();
  await page.getByRole('button', { name: '검색', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Quiet study cafe' })).toBeVisible();
  await expect(page.getByText('근거 확인됨')).toBeVisible();
  expect(submitted[0]).toMatchObject({ query: 'quiet study cafe', personalization_enabled: false });

  await page.getByRole('button', { name: '좋아요' }).click();
  await expect(page.getByRole('status')).toContainText('피드백을 저장했습니다.');
  expect(feedback).toMatchObject({ search_id: 'browser-search-1', document_id: 'quiet-cafe', feedback_type: 'RESULT_LIKE' });

  await page.getByRole('checkbox', { name: '필수 조건' }).check();
  await page.getByRole('button', { name: '수정한 조건으로 다시 검색' }).click();
  await expect.poll(() => submitted.length).toBe(2);
  expect(submitted[1]).toMatchObject({
    context: { criteria_overrides: [{ id: 'quiet-criterion', is_hard_constraint: true }] },
  });

  await expect(page.getByRole('button', { name: '검색', exact: true })).toBeVisible();
  await page.getByLabel('검색어').fill('city park');
  await page.getByRole('button', { name: '검색', exact: true }).click();
  await expect.poll(() => submitted.length).toBe(3);
  expect((submitted[2].context as Record<string, unknown>).criteria_overrides).toBeUndefined();

  await page.getByRole('button', { name: '선호 관리' }).click();
  await page.getByPlaceholder('속성 (예: 소음)').fill('noise_level');
  await page.getByPlaceholder('선호 내용 (예: 조용한 공간)').fill('quiet');
  await page.getByRole('button', { name: '추가' }).click();
  await expect(page.getByText('noise_level: quiet')).toBeVisible();
  await page.getByRole('slider', { name: 'noise_level 중요도' }).press('ArrowRight');
  await expect.poll(() => preferences[0]?.weight).toBeGreaterThan(0.7);
  await page.getByRole('slider', { name: 'noise_level 중요도' })
    .locator('..')
    .getByRole('button', { name: '삭제' })
    .click();
  await expect(page.getByText('저장된 선호가 없습니다.')).toBeVisible();
});

test('network errors are visible to the user', async ({ page }) => {
  await page.route('**/api/v2/search', (route) =>
    route.fulfill({ status: 503, json: { detail: 'Search unavailable' } }),
  );
  await page.goto('/test-harness.html');
  await page.getByLabel('검색어').fill('quiet study cafe');
  await page.getByRole('button', { name: '검색', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Search unavailable');
});

test('a running search can be cancelled', async ({ page }) => {
  let cancelled = false;
  await page.route('**/api/v2/search', (route) =>
    route.fulfill({ json: { search_id: 'cancel-search', status: 'queued' } }),
  );
  await page.route('**/api/v2/search/*/cancel', async (route) => {
    cancelled = true;
    await route.fulfill({ json: { search_id: 'cancel-search', status: 'cancelled' } });
  });
  await page.route('**/api/v2/search/*', async (route) => {
    return route.fulfill({ json: { ...searchResult, search_id: 'cancel-search', status: cancelled ? 'cancelled' : 'running' } });
  });
  await page.goto('/test-harness.html');
  await page.getByLabel('검색어').fill('slow search');
  await page.getByRole('button', { name: '검색', exact: true }).click();
  await page.getByRole('button', { name: '검색 취소' }).click();
  await expect.poll(() => cancelled).toBe(true);
  await expect(page.getByRole('button', { name: '검색', exact: true })).toBeVisible();
});
