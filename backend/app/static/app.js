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

// Botão "Copiar resumo" (Laudos) — o texto vem de um <script type="application/json">
// (escapado com segurança pelo `tojson` do Jinja2, não HTML cru), pra
// manter a mesma forma de copiar que o campo de texto antigo tinha, agora
// com o resumo mostrado em cards em vez de fonte monoespaçada.
function iniciarCopiaDeResumo() {
  document.querySelectorAll("[data-copiar-resumo]").forEach(function (botao) {
    var elemento = document.getElementById(botao.getAttribute("data-copiar-resumo"));
    if (!elemento) return;
    botao.addEventListener("click", function () {
      var texto = JSON.parse(elemento.textContent);
      navigator.clipboard.writeText(texto).then(
        function () { mostrarToast("Resumo copiado.", "sucesso"); },
        function () { mostrarToast("Não foi possível copiar — selecione o texto manualmente.", "erro"); }
      );
    });
  });
}

// Modo escuro (2026-09-28) — o <head> já aplicou o tema salvo antes da
// primeira pintura (ver templates/_tema_inline.html, evita "flash" de tema
// errado); aqui só liga o botão de alternar e mantém o rótulo/ícone certos.
// Sem tema salvo, a página já nasce no tema do sistema operacional via CSS
// (@media prefers-color-scheme) — só grava em localStorage quando a pessoa
// realmente clica no botão (escolha manual explícita).
var CHAVE_TEMA = "elite-sistem-tema";

function temaAtual() {
  var atributo = document.documentElement.getAttribute("data-theme");
  if (atributo === "dark" || atributo === "light") return atributo;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function iniciarAlternanciaTema() {
  var botao = document.querySelector("[data-alternar-tema]");
  if (!botao) return;
  var iconeEscuro = botao.querySelector("[data-icone-tema-escuro]");
  var iconeClaro = botao.querySelector("[data-icone-tema-claro]");
  var rotulo = botao.querySelector("[data-rotulo-tema]");

  function atualizarBotao() {
    var escuro = temaAtual() === "dark";
    if (iconeEscuro) iconeEscuro.style.display = escuro ? "none" : "";
    if (iconeClaro) iconeClaro.style.display = escuro ? "" : "none";
    if (rotulo) rotulo.textContent = escuro ? "Modo claro" : "Modo escuro";
  }

  atualizarBotao();
  botao.addEventListener("click", function () {
    var novo = temaAtual() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", novo);
    try {
      localStorage.setItem(CHAVE_TEMA, novo);
    } catch (e) {
      // localStorage indisponível (ex.: navegação privada) — o tema ainda
      // muda nesta visita, só não fica salvo pra próxima.
    }
    atualizarBotao();
  });
}

// Setores (2026-09-28): mostra/esconde o bloco de checkboxes de abas a
// partir do checkbox "Restringir abas" — `[data-alternar-modulos="id"]`
// controla a visibilidade do elemento com esse id.
function iniciarAlternanciaPorCheckbox() {
  document.querySelectorAll("[data-alternar-modulos]").forEach(function (caixa) {
    var alvo = document.getElementById(caixa.getAttribute("data-alternar-modulos"));
    if (!alvo) return;

    function atualizar() {
      alvo.style.display = caixa.checked ? "" : "none";
    }

    caixa.addEventListener("change", atualizar);
    atualizar();
  });
}

// Setores: dentro de um bloco `[data-modulos-setor="id-do-select"]`, cada
// aba `[data-modulo-operadora="NOME"]` só fica visível se o valor bater com
// a operadora escolhida no <select> indicado (vazio = aba vale pras duas
// operadoras, ex.: Pendências) — a seleção de abas de um setor nunca pode
// sair da operadora dele (regra confirmada pela Clara). Some junto a caixa
// marcada, pra não submeter um módulo escondido/inválido.
function iniciarModulosPorOperadora() {
  document.querySelectorAll("[data-modulos-setor]").forEach(function (bloco) {
    var select = document.getElementById(bloco.getAttribute("data-modulos-setor"));
    if (!select) return;
    var itens = bloco.querySelectorAll("[data-modulo-operadora]");

    function atualizar() {
      var opcaoSelecionada = select.options[select.selectedIndex];
      var nomeOperadora = opcaoSelecionada ? opcaoSelecionada.text : "";
      itens.forEach(function (item) {
        var restrito = item.getAttribute("data-modulo-operadora");
        var mostrar = !restrito || restrito === nomeOperadora;
        item.style.display = mostrar ? "" : "none";
        var caixa = item.querySelector("input");
        if (caixa && !mostrar) caixa.checked = false;
      });
    }

    select.addEventListener("change", atualizar);
    atualizar();
  });
}

// Setores: "Marcar todas" / "Limpar seleção" dentro de um bloco de módulos
// (`[data-marcar-todos-modulos="id"]`/`[data-limpar-modulos="id"]`) — só
// mexe nas caixas que estão visíveis no momento (as escondidas pela
// operadora escolhida, via `iniciarModulosPorOperadora`, ficam de fora).
function iniciarSelecionarTodosModulos() {
  function caixasVisiveis(bloco) {
    return Array.prototype.filter.call(bloco.querySelectorAll("input[type=checkbox]"), function (caixa) {
      return caixa.offsetParent !== null;
    });
  }

  document.querySelectorAll("[data-marcar-todos-modulos]").forEach(function (botao) {
    var alvo = document.getElementById(botao.getAttribute("data-marcar-todos-modulos"));
    if (!alvo) return;
    botao.addEventListener("click", function () {
      caixasVisiveis(alvo).forEach(function (caixa) {
        caixa.checked = true;
      });
    });
  });

  document.querySelectorAll("[data-limpar-modulos]").forEach(function (botao) {
    var alvo = document.getElementById(botao.getAttribute("data-limpar-modulos"));
    if (!alvo) return;
    botao.addEventListener("click", function () {
      caixasVisiveis(alvo).forEach(function (caixa) {
        caixa.checked = false;
      });
    });
  });
}

// Pop-up de suporte (2026-09-28) — o botão flutuante abre o <dialog> via o
// mesmo mecanismo genérico de modal (`data-abrir-confirmacao`, ver
// `iniciarModaisDeConfirmacao`); aqui só o envio, por fetch (não form/
// redirect — o pop-up pode ser aberto de qualquer página do sistema).
function iniciarPopupSuporte() {
  var botaoEnviar = document.getElementById("botao-enviar-suporte");
  var modal = document.getElementById("popup-suporte");
  var campoAssunto = document.getElementById("suporte-assunto");
  var campoDescricao = document.getElementById("suporte-descricao");
  if (!botaoEnviar || !modal || !campoAssunto || !campoDescricao) return;
  var rotuloOriginal = botaoEnviar.textContent;

  function limparCampos() {
    campoAssunto.value = "";
    campoDescricao.value = "";
  }

  botaoEnviar.addEventListener("click", function () {
    var assunto = campoAssunto.value.trim();
    var descricao = campoDescricao.value.trim();
    if (!assunto || !descricao) {
      mostrarToast("Preencha o assunto e a descrição do chamado.", "erro");
      return;
    }

    botaoEnviar.disabled = true;
    botaoEnviar.textContent = "Enviando...";

    fetch("/app/suporte/chamado", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assunto: assunto, descricao: descricao }),
    })
      .then(function (resposta) {
        return resposta.json()
          .catch(function () {
            throw new Error("Não foi possível enviar o chamado — atualize a página e tente de novo.");
          })
          .then(function (dados) {
            if (!resposta.ok) throw new Error(dados.erro || "Não foi possível enviar o chamado.");
            return dados;
          });
      })
      .then(function () {
        mostrarToast("Chamado enviado! A gente retorna assim que possível.", "sucesso");
        limparCampos();
        modal.close();
      })
      .catch(function (erro) {
        mostrarToast(erro.message, "erro");
      })
      .finally(function () {
        botaoEnviar.disabled = false;
        botaoEnviar.textContent = rotuloOriginal;
      });
  });

  modal.addEventListener("close", limparCampos);
}

// Botão "Copiar texto" (Cartas, 2026-09-29, a pedido da Clara: "preciso que
// exatamente o mesmo conteúdo que vem escrito no PDF... venha escrito em
// formato de texto pra copiar e colar"). Diferente do "Copiar resumo" de
// Laudos, o texto não está pronto na página ao carregar — depende dos
// campos do formulário (autor/réu/CPF/link etc.), então busca no servidor
// via fetch (mesma validação usada pra gerar o PDF: link de audiência,
// dígitos do CPF) e só então copia pro clipboard.
function iniciarCopiaDeTextoCartas() {
  document.querySelectorAll("[data-copiar-texto-url]").forEach(function (botao) {
    var form = botao.closest("form");
    if (!form) return;
    botao.addEventListener("click", function () {
      if (!form.reportValidity()) return;
      var rotuloOriginal = botao.textContent;
      botao.disabled = true;
      botao.textContent = "Copiando...";
      fetch(botao.getAttribute("data-copiar-texto-url"), { method: "POST", body: new FormData(form) })
        .then(function (resposta) {
          return resposta.json().then(function (dados) {
            if (!resposta.ok) throw new Error(dados.erro || "Não foi possível gerar o texto.");
            return dados;
          });
        })
        .then(function (dados) { return navigator.clipboard.writeText(dados.texto); })
        .then(function () { mostrarToast("Texto copiado.", "sucesso"); })
        .catch(function (erro) {
          mostrarToast(erro.message || "Não foi possível copiar — tente de novo.", "erro");
        })
        .finally(function () {
          botao.disabled = false;
          botao.textContent = rotuloOriginal;
        });
    });
  });
}

// Seleção em massa de empresas (2026-10-06, a pedido da Clara: "selecionar
// e apagar empresas em massa, além de realocá-las em massa se necessário").
// Checkboxes `.chk-empresa-massa` (uma por linha) + `#chk-empresa-todas`
// (marca/desmarca todas) alimentam uma barra de ações (`#barra-selecao-
// empresas`) que só aparece com pelo menos 1 selecionada. Os botões dessa
// barra (`[data-abrir-selecao-massa="id-do-modal"]`) abrem um dos dois
// modais de lote: ao abrir, os ids selecionados são injetados como campos
// ocultos dentro do <form> de cada modal (`[data-ids-selecionados]`) — as
// próprias caixas de seleção não pertencem a nenhum form (vivem soltas na
// tabela), então isso é o jeito de levar a seleção até o POST certo. No
// modal de excluir, o campo de empresa de destino só aparece (e só fica
// obrigatório) se alguma selecionada tiver vínculo — ver
// `contar_vinculos_empresa`/`_ENTIDADES_VINCULADAS` no backend. Em ambos os
// modais, a própria empresa selecionada nunca aparece como opção de destino.
//
// Bug real reportado pela Clara (2026-10-06, "eu seleciono o campo pra
// mover o histórico, e mesmo assim não apaga todos os selecionados"):
// usando "Selecionar todas", a empresa que ela queria manter como destino
// também ficava marcada pra exclusão — o backend recusa isso (não dá pra
// uma empresa ser destino de si mesma), e a operação inteira falhava sem
// deixar claro o motivo. Correção: ao escolher uma empresa no campo de
// destino, se ela estiver marcada pra exclusão/realocação, a caixa dela é
// desmarcada automaticamente (`iniciarAutoDesmarcarDestino`) — o fluxo
// natural de "selecionar tudo e escolher uma sobrevivente" passa a
// funcionar sem precisar desmarcar nada manualmente.
function iniciarSelecaoEmMassaDeEmpresas() {
  var caixaTodas = document.getElementById("chk-empresa-todas");
  var caixas = Array.prototype.slice.call(document.querySelectorAll(".chk-empresa-massa"));
  var barra = document.getElementById("barra-selecao-empresas");
  var contador = document.getElementById("contador-selecao-empresas");
  if (!caixas.length || !barra) return;

  function selecionadas() {
    return caixas.filter(function (caixa) { return caixa.checked; });
  }

  function atualizarBarra() {
    var sel = selecionadas();
    barra.style.display = sel.length ? "" : "none";
    if (contador) contador.textContent = sel.length + " selecionada(s)";
    if (caixaTodas) {
      caixaTodas.checked = sel.length > 0 && sel.length === caixas.length;
      caixaTodas.indeterminate = sel.length > 0 && sel.length < caixas.length;
    }
  }

  caixas.forEach(function (caixa) {
    caixa.addEventListener("change", atualizarBarra);
  });
  if (caixaTodas) {
    caixaTodas.addEventListener("change", function () {
      caixas.forEach(function (caixa) { caixa.checked = caixaTodas.checked; });
      atualizarBarra();
    });
  }

  function preencherIdsOcultos(modal, idsSelecionados) {
    var contorno = modal.querySelector("[data-ids-selecionados]");
    if (!contorno) return;
    contorno.innerHTML = "";
    idsSelecionados.forEach(function (id) {
      var oculto = document.createElement("input");
      oculto.type = "hidden";
      oculto.name = "empresa_ids";
      oculto.value = id;
      contorno.appendChild(oculto);
    });
  }

  // Mantém o modal aberto em sincronia com a seleção atual: reconstrói os
  // campos ocultos, o contador, a exigência do campo de destino (modal de
  // excluir) e quais empresas aparecem como opção de destino (nunca uma
  // que esteja marcada). Chamada ao abrir o modal e de novo sempre que a
  // seleção muda enquanto ele está aberto (ver `iniciarAutoDesmarcarDestino`).
  function atualizarModalAberto(modal) {
    var sel = selecionadas();
    var idsSelecionados = sel.map(function (caixa) { return caixa.value; });
    preencherIdsOcultos(modal, idsSelecionados);

    modal.querySelectorAll("[data-contador-modal]").forEach(function (span) {
      span.textContent = sel.length;
    });

    var blocoDestino = modal.querySelector("[data-bloco-destino-obrigatorio]");
    if (blocoDestino) {
      var algumComVinculo = sel.some(function (caixa) { return caixa.getAttribute("data-vinculo") === "1"; });
      blocoDestino.style.display = algumComVinculo ? "" : "none";
      var selectCondicional = blocoDestino.querySelector("select");
      if (selectCondicional) selectCondicional.required = algumComVinculo;
    }

    modal.querySelectorAll("select").forEach(function (select) {
      select.querySelectorAll("[data-opcao-destino]").forEach(function (opcao) {
        opcao.hidden = idsSelecionados.indexOf(opcao.value) !== -1;
      });
    });
  }

  function iniciarAutoDesmarcarDestino(modal) {
    var select = modal.querySelector("select[name=empresa_destino_id]");
    if (!select) return;
    select.addEventListener("change", function () {
      if (!select.value) return;
      var caixaDestino = caixas.filter(function (c) { return c.value === select.value; })[0];
      if (caixaDestino && caixaDestino.checked) {
        caixaDestino.checked = false;
        atualizarBarra();
        atualizarModalAberto(modal);
        mostrarToast(
          "A empresa escolhida como destino foi retirada da seleção (ela não pode ser destino de si mesma).",
          "sucesso"
        );
      }
    });
  }

  document.querySelectorAll("#modal-excluir-em-massa, #modal-realocar-em-massa").forEach(iniciarAutoDesmarcarDestino);

  document.querySelectorAll("[data-abrir-selecao-massa]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      var modal = document.getElementById(botao.getAttribute("data-abrir-selecao-massa"));
      if (!modal || !selecionadas().length) return;

      modal.querySelectorAll("select").forEach(function (select) { select.value = ""; });
      atualizarModalAberto(modal);
      modal.showModal();
    });
  });

  atualizarBarra();
}

document.addEventListener("DOMContentLoaded", function () {
  iniciarZonasDeUpload();
  iniciarValidacaoDeUpload();
  iniciarAlternanciaTipoRelatorio();
  iniciarModaisDeConfirmacao();
  iniciarConfirmacaoPorTexto();
  iniciarCopiaDeResumo();
  iniciarCopiaDeTextoCartas();
  iniciarAlternanciaTema();
  iniciarAlternanciaPorCheckbox();
  iniciarModulosPorOperadora();
  iniciarSelecionarTodosModulos();
  iniciarPopupSuporte();
  iniciarSelecaoEmMassaDeEmpresas();
});
