<script>
  let { assignments = [], submissions = [] } = $props();

  let selectedAssignment = $state(null);

  // Map submission by assignment_id
  const submissionsMap = $derived(
    submissions.reduce((acc, sub) => {
      acc[sub.assignment_id] = sub;
      return acc;
    }, {})
  );
</script>

<div>
  {#if selectedAssignment}
    <div style="margin-bottom: 16px;">
      <button class="btn btn-secondary btn-sm" onclick={() => (selectedAssignment = null)}>
        ← Back to All Assignments
      </button>
    </div>

    <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; padding: 28px; box-shadow: var(--shadow-sm);">
      <div style="border-bottom: 1px solid var(--canvas-border); padding-bottom: 16px; margin-bottom: 20px;">
        <h1 style="font-size: 22px; font-weight: 700; color: var(--canvas-navy);">{selectedAssignment.name}</h1>
        <div style="font-size: 13px; color: var(--canvas-text-muted); margin-top: 6px; display: flex; gap: 16px;">
          <span>Points: <strong>{selectedAssignment.points_possible ?? 'N/A'}</strong></span>
          {#if selectedAssignment.due_at}
            <span>Due: <strong>{new Date(selectedAssignment.due_at).toLocaleString()}</strong></span>
          {/if}
        </div>
      </div>

      <!-- My Personal Submission & Feedback Card -->
      {#if submissionsMap[selectedAssignment.id]}
        {@const sub = submissionsMap[selectedAssignment.id]}
        <div style="background: #F8F9FA; border: 1px solid var(--canvas-border); border-radius: 8px; padding: 18px; margin-bottom: 24px;">
          <h3 style="font-size: 15px; font-weight: 600; color: var(--canvas-navy); margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
            <span>🎓 Your Submission & Feedback</span>
            {#if sub.grade !== null && sub.grade !== undefined}
              <span class="offline-badge" style="background: #E6F4EA; color: #137333;">
                Grade: {sub.grade} {sub.score !== null ? `(${sub.score} pts)` : ''}
              </span>
            {/if}
          </h3>

          <div style="font-size: 13px; color: var(--canvas-text-muted); margin-bottom: 12px;">
            {#if sub.submitted_at}
              Submitted on: {new Date(sub.submitted_at).toLocaleString()}
            {:else}
              Status: Not submitted or offline submission
            {/if}
          </div>

          {#if sub.body}
            <div style="background: #fff; border: 1px solid var(--canvas-border); padding: 12px; border-radius: 6px; font-size: 13px; margin-bottom: 12px;">
              <strong>Submitted Content:</strong>
              <div style="margin-top: 6px;">{sub.body}</div>
            </div>
          {/if}

          {#if sub.submission_comments && sub.submission_comments.length > 0}
            <div style="margin-top: 12px;">
              <strong style="font-size: 13px;">Teacher Feedback / Comments:</strong>
              <div style="margin-top: 8px; display: flex; flex-direction: column; gap: 8px;">
                {#each sub.submission_comments as comm}
                  <div style="background: #fff; border: 1px solid #E0E4E8; border-radius: 6px; padding: 10px 14px; font-size: 13px;">
                    <div style="font-weight: 600; color: var(--canvas-navy); font-size: 12px;">
                      {comm.author_name || 'Instructor'} ({comm.created_at ? new Date(comm.created_at).toLocaleDateString() : ''}):
                    </div>
                    <div style="margin-top: 4px; color: var(--canvas-text);">{comm.comment}</div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}

      <!-- Assignment Prompt Body -->
      <div class="wiki-content">
        {#if selectedAssignment.description_rewritten || selectedAssignment.description}
          {@html selectedAssignment.description_rewritten || selectedAssignment.description}
        {:else}
          <div style="color: var(--canvas-text-muted); padding: 20px 0;">No written description for this assignment.</div>
        {/if}
      </div>
    </div>
  {:else}
    <div style="background: #fff; border: 1px solid var(--canvas-border); border-radius: 8px; overflow: hidden; box-shadow: var(--shadow-sm);">
      <div style="padding: 16px 20px; border-bottom: 1px solid var(--canvas-border); font-size: 16px; font-weight: 600;">
        Assignments ({assignments.length})
      </div>

      {#if assignments.length === 0}
        <div style="padding: 40px; text-align: center; color: var(--canvas-text-muted);">
          No assignments found.
        </div>
      {:else}
        {#each assignments as assign}
          {@const sub = submissionsMap[assign.id]}
          <div
            class="module-item"
            onclick={() => (selectedAssignment = assign)}
            role="button"
            tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && (selectedAssignment = assign)}
            style="padding: 16px 20px;"
          >
            <span style="font-size: 18px; margin-right: 8px;">📝</span>
            <div style="flex: 1;">
              <div style="font-size: 15px; font-weight: 600; color: var(--canvas-navy);">
                {assign.name}
              </div>
              <div style="font-size: 12px; color: var(--canvas-text-muted); margin-top: 3px; display: flex; gap: 12px;">
                <span>Points: {assign.points_possible ?? 'N/A'}</span>
                {#if assign.due_at}
                  <span>Due: {new Date(assign.due_at).toLocaleDateString()}</span>
                {/if}
              </div>
            </div>

            {#if sub && sub.grade !== null && sub.grade !== undefined}
              <span class="offline-badge" style="background: #E6F4EA; color: #137333; font-size: 12px;">
                Score: {sub.grade}
              </span>
            {/if}

            <button class="btn btn-secondary btn-sm" style="margin-left: 12px;">View Details →</button>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>
