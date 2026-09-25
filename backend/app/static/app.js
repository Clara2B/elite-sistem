// Elite Sistem — comportamento das páginas HTML (Fase 6).
// Sem framework/CDN externo — vanilla JS, carregado direto de /static.

function mostrarToast(texto, tipo) {
  var div = document.createElement("div");
  div.className = "mensagem " + (tipo || "erro");
  div.setAttribute("role", "alert");

  var span = document.createElement("span");
  span.textContent = texto;
  div.appendChild(span);

  var botao = document.createElement("button");
  botao.type = "button";
  botao.className = "fechar-toast";
  botao.setAttribute("aria-label", "Fechar");
  botao.innerHTML = "&times;";
  botao.addEventListener("click", function () {
    div.remove();
  });
  div.appendChild(botao);

  document.body.appendChild(div);
  return div;
}

function iniciarZonasDeUpload() {
  document.querySelectorAll("[data-upload]").forEach(function (zona) {
    var input = zona.querySelector("[data-upload-input]");
    var texto = zona.querySelector("[data-upload-texto]");
    if (!input || !texto) return;
    var textoOriginal = texto.textContent;

    input.addEventListener("change", function () {
      zona.classList.remove("upload-erro");
      if (input.files && input.files.length > 0) {
        texto.textContent = input.files[0].name;
        zona.classList.add("upload-com-arquivo");
      } else {
        texto.textContent = textoOriginal;
        zona.classList.remove("upload-com-arquivo");
      }
    });
  });
}

// Troca a bolha nativa do navegador ("Selecione um arquivo.") por um toast
// no estilo do resto do sistema — só a validação de arquivo obrigatório,
// as outras validações HTML5 (email, required de texto) continuam nativas.
function iniciarValidacaoDeUpload() {
  document.querySelectorAll("form").forEach(function (form) {
    var camposArquivo = form.querySelectorAll("input[type=file][required]");
    if (camposArquivo.length === 0) return;

    // A validação nativa do HTML5 nunca dispara o evento "submit" quando um
    // campo obrigatório está vazio (ela aborta o envio antes disso) — então
    // um listener de "submit" sozinho nunca seria chamado para mostrar o
    // toast. `noValidate` desliga a validação nativa (só afeta este form, que
    // não tem outro campo obrigatório além do arquivo) e a checagem abaixo
    // assume o lugar dela.
    form.noValidate = true;

    form.addEventListener("submit", function (evento) {
      for (var i = 0; i < camposArquivo.length; i++) {
        var campo = camposArquivo[i];
        if (!campo.files || campo.files.length === 0) {
          evento.preventDefault();
          var zona = campo.closest("[data-upload]");
          if (zona) zona.classList.add("upload-erro");
          mostrarToast("Selecione um arquivo antes de importar.", "erro");
          return;
        }
      }
    });
  });
}

// Modal de confirmação genérico — usado hoje só por "excluir empresa", mas
// serve para qualquer ação perigosa futura: um <dialog data-confirmar>
// escondido na página, aberto por um botão com data-abrir-confirmacao
// apontando pro id do dialog, com o formulário de verdade dentro do modal.
function iniciarModaisDeConfirmacao() {
  document.querySelectorAll("[data-abrir-confirmacao]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var idModal = botao.getAttribute("data-abrir-confirmacao");
      var modal = document.getElementById(idModal);
      if (!modal) return;
      var nomeAlvo = botao.getAttribute("data-nome-alvo");
      if (nomeAlvo) {
        modal.querySelectorAll("[data-nome-alvo-destino]").forEach(function (el) {
          el.textContent = nomeAlvo;
        });
      }
      modal.showModal();
    });
  });

  document.querySelectorAll("dialog.modal-confirmacao [data-fechar-modal]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      botao.closest("dialog").close();
    });
  });
}

// Trava o botão de confirmar até a pessoa digitar a palavra pedida — pra
// ações muito mais destrutivas que um "excluir" comum (ex.: apagar TODO o
// histórico de um módulo, não só um registro), onde o modal sozinho já não
// parece proteção suficiente. Campo com [data-confirmar-texto="PALAVRA"]
// destrava o botão com [data-confirmar-alvo] quando o texto digitado bate
// exatamente (sem diferenciar maiúsculas) com PALAVRA.
function iniciarConfirmacaoPorTexto() {
  document.querySelectorAll("[data-confirmar-texto]").forEach(function (campo) {
    var modal = campo.closest("dialog");
    var botao = modal ? modal.querySelector("[data-confirmar-alvo]") : null;
    if (!botao) return;
    var esperado = campo.getAttribute("data-confirmar-texto").toUpperCase();

    botao.disabled = true;
    campo.addEventListener("input", function () {
      botao.disabled = campo.value.trim().toUpperCase() !== esperado;
    });

    // Limpa o campo (e retrava o botão) toda vez que o modal fecha, pra não
    // ficar destravado se a pessoa abrir de novo sem digitar nada.
    modal.addEventListener("close", function () {
      campo.value = "";
      botao.disabled = true;
    });
  });
}

// Relatório de Gestão de Processos: o campo "Empresa" só faz sentido pro
// tipo "Por empresa" — fica escondido (e desabilitado, pra não submeter
// junto) quando o tipo selecionado é "Geral". `[data-mostrar-se-tipo="valor"]`
// marca o bloco com o valor de "Tipo de relatório" em que ele deve aparecer.
function iniciarAlternanciaTipoRelatorio() {
  var tipo = document.getElementById("tipo");
  var campos = document.querySelectorAll("[data-mostrar-se-tipo]");
  if (!tipo || !campos.length) return;

  function atualizar() {
    var valor = tipo.value;
    campos.forEach(function (campo) {
      var mostrar = campo.getAttribute("data-mostrar-se-tipo") === valor;
      campo.style.display = mostrar ? "" : "none";
      var entrada = campo.querySelector("input, select");
      if (entrada) entrada.disabled = !mostrar;
    });
  }

  tipo.addEventListener("change", atualizar);
  atualizar();
}

document.addEventListener("DOMContentLoaded", function () {
  iniciarZonasDeUpload();
  iniciarValidacaoDeUpload();
  iniciarAlternanciaTipoRelatorio();
  iniciarModaisDeConfirmacao();
  iniciarConfirmacaoPorTexto();
});
