// Criado por OpenAI Codex em 23/06/2026.
// Implementa o drag-and-drop do kanban com atualização assíncrona do status da tarefa.

(function () {
  const board = document.querySelector(".tarefas-kanban-board");
  if (!board) {
    return;
  }

  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value || getCookie("csrftoken");
  let currentCard = null;

  board.querySelectorAll(".tarefas-kanban-card").forEach((card) => {
    card.addEventListener("dragstart", () => {
      currentCard = card;
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
      currentCard = null;
      board.querySelectorAll(".tarefas-kanban-dropzone").forEach((zone) => zone.classList.remove("is-over"));
    });
  });

  board.querySelectorAll(".tarefas-kanban-dropzone").forEach((zone) => {
    zone.addEventListener("dragover", (event) => {
      event.preventDefault();
      zone.classList.add("is-over");
    });
    zone.addEventListener("dragleave", () => {
      zone.classList.remove("is-over");
    });
    zone.addEventListener("drop", async (event) => {
      event.preventDefault();
      zone.classList.remove("is-over");
      if (!currentCard) {
        return;
      }
      const draggedCard = currentCard;
      const novoStatus = zone.dataset.status;
      const taskId = draggedCard.dataset.taskId;
      try {
        const response = await fetch(`/tarefas/${taskId}/status/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": csrfToken,
          },
          body: new URLSearchParams({ status: novoStatus }).toString(),
        });
        const data = await response.json();
        if (!response.ok || !data.ok) {
          throw new Error(data.error || "Não foi possível mover a tarefa.");
        }
        const emptyState = zone.querySelector(".tarefas-kanban-empty");
        if (emptyState) {
          emptyState.remove();
        }
        zone.appendChild(draggedCard);
        updateCard(draggedCard, data.tarefa);
        updateCounts(board);
      } catch (error) {
        window.alert(error.message);
      }
    });
  });

  function updateCard(card, tarefa) {
    const progressBar = card.querySelector(".progress-bar");
    const progressMeta = card.querySelector(".tarefas-progress-meta");
    const link = card.querySelector(".tarefas-link-title");
    link.textContent = `#${tarefa.id} ${tarefa.titulo}`;
    link.href = tarefa.detail_url;
    progressBar.style.width = `${tarefa.progresso.percentual}%`;
    progressBar.className = `progress-bar bg-${tarefa.progresso.cor === "danger-strong" ? "danger" : tarefa.progresso.cor}`;
    progressMeta.innerHTML = `<strong>${tarefa.progresso.percentual.toFixed(1)}%</strong><span${tarefa.progresso.atrasada ? ' class="text-danger fw-semibold"' : ""}>${tarefa.prazo}</span>`;
  }

  function updateCounts(root) {
    root.querySelectorAll(".tarefas-kanban-column").forEach((column) => {
      const count = column.querySelectorAll(".tarefas-kanban-card").length;
      const badge = column.querySelector(".tarefas-kanban-column-header .badge");
      if (badge) {
        badge.textContent = count;
      }
      const empty = column.querySelector(".tarefas-kanban-empty");
      if (count === 0 && !empty) {
        const placeholder = document.createElement("div");
        placeholder.className = "tarefas-kanban-empty";
        placeholder.textContent = "Sem tarefas nesta coluna.";
        column.querySelector(".tarefas-kanban-dropzone").appendChild(placeholder);
      } else if (count > 0 && empty) {
        empty.remove();
      }
    });
  }

  function getCookie(name) {
    const cookieValue = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith(`${name}=`));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  }
})();
